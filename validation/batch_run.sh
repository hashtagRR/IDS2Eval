#!/bin/bash
# General GCP Batch task: fetches the staged code, wheels, config and data
# from GCS, installs ids2eval offline, runs RUN_CMD, and keeps its output
# mirrored to GCS so a failed or preempted attempt resumes where it stopped.
#
# RUN_CMD runs in $WORK with the venv on PATH. It should write everything to
# $OUT (exported); the config is at $WORK/config.yaml and the data under
# $WORK/data/. An ids2eval audit resumes from out/.checkpoint when the config
# sets audit.checkpoint: true and output.dir: /tmp/ids2eval_task/out.
#
# Layout under $RESULT_URI:
#   out/                 everything RUN_CMD wrote (minus .cache/, the split
#                        cache, which is large and rebuilt on a retry)
#   logs/run.log         RUN_CMD's output, appended across attempts
#   logs/attempt_<n>.log this script's own log for attempt n
#   logs/memlog.txt      free -m every 10s, appended across attempts
#   host.txt             VM shape of the latest attempt
#
# Exit codes: 2 fetch failed, 4 venv, 5 pip, 6 RUN_CMD failed, 7 upload. The
# job's lifecycle policy fails the task on these instead of retrying, so only
# a preemption or VM loss triggers an automatic retry. Resubmit with the same
# RESULT_URI to resume after a fix.
#
# Environment: CODE_URI, WHEELS_URI, CONFIG_URI, DATA_URI, RESULT_URI, RUN_CMD.
# The project's org policy denies external IPs, so the VM has no apt or PyPI.
set -u
export PATH="${PATH:+$PATH:}/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export HOME="${HOME:-/root}"
PY=/usr/bin/python3
export WORK=/tmp/ids2eval_task
export OUT="$WORK/out"
LOGS="$WORK/logs"
ATTEMPT="${BATCH_TASK_RETRY_ATTEMPT:-0}"
rm -rf "$WORK"; mkdir -p "$WORK/data" "$OUT" "$LOGS" "$WORK/ids2eval_src"; cd "$WORK" || exit 1

ATTEMPT_LOG="$LOGS/attempt_${ATTEMPT}.log"
log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$ATTEMPT_LOG"; }
push_logs() { gcloud storage rsync "$LOGS" "$RESULT_URI/logs" --quiet 2>/dev/null; }
push_out() { gcloud storage rsync -r -x '(.*\.tmp$|.*\.part$|\.cache/.*)' "$OUT" "$RESULT_URI/out" --quiet 2>/dev/null; }

log "stage setup: attempt $ATTEMPT on $(hostname), $(nproc) vCPU, $(free -g | awk '/Mem/ {print $2}') GB"
{ nproc; free -g; df -h /tmp; uname -a; echo "attempt $ATTEMPT"; } > "$WORK/host.txt"
gcloud storage cp "$WORK/host.txt" "$RESULT_URI/host.txt" --quiet 2>/dev/null
gcloud storage rsync "$RESULT_URI/logs" "$LOGS" --quiet 2>/dev/null
log "stage resume: pulling previous output from $RESULT_URI/out"
if gcloud storage rsync -r "$RESULT_URI/out" "$OUT" --quiet 2>/dev/null; then
    log "previous output: $(find "$OUT" -type f | wc -l) files"
else
    log "no previous output, starting fresh"
fi

( while true; do { date -u +%FT%TZ; echo "attempt $ATTEMPT"; free -m; echo; } >> "$LOGS/memlog.txt"; sleep 10; done ) &
MEMLOG_PID=$!

log "stage fetch: code, config, wheels, data"
gcloud storage cp "$CODE_URI" code.tar.gz --quiet || { log "code fetch failed"; push_logs; exit 2; }
gcloud storage cp "$CONFIG_URI" config.yaml --quiet || { log "config fetch failed"; push_logs; exit 2; }
tar xzf code.tar.gz -C ids2eval_src || { log "code unpack failed"; push_logs; exit 2; }
mkdir -p wheels && gcloud storage cp "$WHEELS_URI/*.whl" wheels/ --quiet || { log "wheel fetch failed"; push_logs; exit 2; }
gcloud storage cp "$DATA_URI"/* data/ --quiet || { log "data fetch failed"; push_logs; exit 2; }
log "fetched $(ls data | wc -l) data files, $(du -sh data | cut -f1)"

log "stage install"
PIP_WHEEL=$(ls wheels/pip-*.whl | head -1)
"$PY" -m venv --without-pip venv || { log "venv creation failed"; push_logs; exit 4; }
venv/bin/python "$PIP_WHEEL/pip" install -q --no-index "$PIP_WHEEL" || { log "pip bootstrap failed"; push_logs; exit 5; }
venv/bin/python -m pip install -q --no-index --find-links wheels "./ids2eval_src" \
    || { log "pip install failed"; push_logs; exit 5; }
export PATH="$WORK/venv/bin:$PATH"
log "$(python --version 2>&1), ids2eval $(python -c 'from importlib.metadata import version; print(version("ids2eval"))' 2>&1)"

( while true; do sleep 60; push_out; push_logs; done ) &
SYNC_PID=$!

log "stage run: $RUN_CMD"
echo "===== attempt $ATTEMPT $(date -u +%FT%TZ) =====" >> "$LOGS/run.log"
start=$(date +%s)
PYTHONUNBUFFERED=1 bash -c "$RUN_CMD" >> "$LOGS/run.log" 2>&1
status=$?
log "stage run: exit $status after $(( $(date +%s) - start ))s"

kill "$SYNC_PID" "$MEMLOG_PID" 2>/dev/null
wait "$SYNC_PID" "$MEMLOG_PID" 2>/dev/null

log "stage upload"
cp config.yaml "$OUT/job_config.yaml"
push_out || { log "final output upload failed"; push_logs; exit 7; }
push_logs
if [ "$status" -ne 0 ]; then
    log "run failed; see logs/run.log. Resubmit with the same RESULT_URI to resume."
    push_logs
    exit 6
fi
log "done"
push_logs
exit 0
