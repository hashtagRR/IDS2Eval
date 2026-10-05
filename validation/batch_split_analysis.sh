#!/bin/bash
# GCP Batch task for validation/batch_split_analysis.py. Fetches the staged code,
# dataset and config from GCS, runs the staged analysis, and keeps everything it
# writes mirrored to GCS so a failed or preempted attempt resumes where it stopped.
#
# Layout under $RESULT_URI:
#   out/state.json             per-stage status, attempts, start/finish times, errors
#   out/homogeneity.json       homogeneity stage result
#   out/seeds/seed_<n>.json    one file per seed, filled unit by unit
#   out/cache/combined.parquet the loaded dataset, so a retry skips CSV parsing
#   out/class_sensitive_seeds.json, out/model_sensitivity.json   summarize stage
#   logs/analysis.log          the Python log, appended across attempts
#   logs/attempt_<n>.log       this script's own log for attempt n
#   logs/memlog.txt            free -m every 10s, appended across attempts
#   host.txt                   VM shape of the latest attempt
#
# Exit codes: 2 fetch failed, 4 venv, 5 pip, 6 analysis stage failed, 7 upload.
# The job's lifecycle policy fails the task on these instead of retrying, so
# only a preemption or VM loss triggers an automatic retry. To rerun after a
# fix, resubmit with the same RESULT_URI; FORCE_STAGES reruns finished stages.
#
# Environment: CODE_URI, DATA_URI, CONFIG_URI, RESULT_URI, N_SEEDS, FORCE_STAGES (optional).
set -u
export PATH="${PATH:+$PATH:}/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export HOME="${HOME:-/root}"
export DEBIAN_FRONTEND=noninteractive
PY=/usr/bin/python3
WORK=/tmp/ids2eval_task
OUT="$WORK/out"
LOGS="$WORK/logs"
ATTEMPT="${BATCH_TASK_RETRY_ATTEMPT:-0}"
rm -rf "$WORK"; mkdir -p "$WORK/data" "$OUT" "$LOGS" "$WORK/ids2eval_src"; cd "$WORK" || exit 1

ATTEMPT_LOG="$LOGS/attempt_${ATTEMPT}.log"
log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$ATTEMPT_LOG"; }
push_logs() {
    gcloud storage rsync "$LOGS" "$RESULT_URI/logs" --quiet 2>/dev/null
}
push_out() {
    gcloud storage rsync -r -x '.*\.tmp$' "$OUT" "$RESULT_URI/out" --quiet 2>/dev/null
}

log "stage setup: attempt $ATTEMPT on $(hostname), $(nproc) vCPU, $(free -g | awk '/Mem/ {print $2}') GB"
{ nproc; free -g; uname -a; echo "attempt $ATTEMPT"; } > "$WORK/host.txt"
gcloud storage cp "$WORK/host.txt" "$RESULT_URI/host.txt" --quiet 2>/dev/null

# Earlier attempts' logs come back first, so this attempt appends to them.
gcloud storage rsync "$RESULT_URI/logs" "$LOGS" --quiet 2>/dev/null
log "stage resume: pulling previous output from $RESULT_URI/out"
if gcloud storage rsync -r "$RESULT_URI/out" "$OUT" --quiet 2>/dev/null; then
    log "previous state: $(cat "$OUT/state.json" 2>/dev/null | tr -d '\n ' | cut -c1-600)"
else
    log "no previous output, starting fresh"
fi

(
    while true; do
        { date -u +%FT%TZ; echo "attempt $ATTEMPT"; free -m; echo; } >> "$LOGS/memlog.txt"
        sleep 10
    done
) &
MEMLOG_PID=$!

log "stage fetch: code and config"
gcloud storage cp "$CODE_URI" code.tar.gz --quiet || { log "code fetch failed"; push_logs; exit 2; }
gcloud storage cp "$CONFIG_URI" config.yaml --quiet || { log "config fetch failed"; push_logs; exit 2; }
tar xzf code.tar.gz -C ids2eval_src || { log "code unpack failed"; push_logs; exit 2; }
if [ -f "$OUT/cache/combined.parquet" ]; then
    log "stage fetch: cached combined.parquet present, skipping raw data download"
else
    log "stage fetch: raw data from $DATA_URI"
    gcloud storage cp "$DATA_URI"/* data/ --quiet || { log "data fetch failed"; push_logs; exit 2; }
    log "fetched $(ls data | wc -l) files, $(du -sh data | cut -f1)"
fi

log "stage install"
if ! "$PY" -c "import ensurepip, venv" >/dev/null 2>&1; then
    apt-get update -qq && apt-get install -y -qq python3-venv python3-pip >/dev/null
fi
"$PY" -m venv venv || { log "venv creation failed"; push_logs; exit 4; }
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q "./ids2eval_src" || { log "pip install failed"; push_logs; exit 5; }
log "$(venv/bin/python3 --version 2>&1), ids2eval $(venv/bin/python3 -c 'from importlib.metadata import version; print(version("ids2eval"))' 2>&1)"

(
    while true; do
        sleep 60
        push_out
        push_logs
    done
) &
SYNC_PID=$!

log "stage analysis: start (N_SEEDS=$N_SEEDS, FORCE_STAGES=${FORCE_STAGES:-none})"
echo "===== attempt $ATTEMPT $(date -u +%FT%TZ) =====" >> "$LOGS/analysis.log"
start=$(date +%s)
FORCE_STAGES="${FORCE_STAGES:-}" PYTHONUNBUFFERED=1 \
    venv/bin/python3 ids2eval_src/validation/batch_split_analysis.py config.yaml "$OUT" "$N_SEEDS" \
    >> "$LOGS/analysis.log" 2>&1
status=$?
log "stage analysis: exit $status after $(( $(date +%s) - start ))s"
log "state: $(cat "$OUT/state.json" 2>/dev/null | tr -d '\n ' | cut -c1-800)"

kill "$SYNC_PID" "$MEMLOG_PID" 2>/dev/null
wait "$SYNC_PID" "$MEMLOG_PID" 2>/dev/null

log "stage upload"
cp config.yaml "$OUT/config.yaml"
push_out || { log "final output upload failed"; push_logs; exit 7; }
push_logs
if [ "$status" -ne 0 ]; then
    log "analysis failed; see logs/analysis.log and out/state.json. Resubmit with the same RESULT_URI to resume."
    push_logs
    exit 6
fi
log "done"
push_logs
exit 0
