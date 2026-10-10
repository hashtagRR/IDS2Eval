#!/usr/bin/env bash
# Cloud Batch runnable for the post-freeze analyses too large for the dev VM:
#   - validation/host_holdout.py on BoT-IoT (3.7M rows; ToN-IoT ran locally)
#   - validation/port_protocol_lookup_stream.py on CIC-IDS2018 (16.2M rows)
#     and CICDDoS2019 (70.4M rows)
# Each step is skipped when its result is already in the JSON it writes, so a
# spot preemption resumes. Inputs (environment): CODE_URI (tar.gz of the
# repository), WHEELS_URI (offline Python 3.11 wheels), DATA_URI (prefix with
# bot-iot-official/, cic-ids2018/ and cic-ddos2019/), RESULT_URI.
set -u
export PATH="${PATH:+$PATH:}/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export HOME="${HOME:-/root}"
WORK=/tmp/leftovers_task
LOGS="$WORK/logs"
ATTEMPT="${BATCH_TASK_RETRY_ATTEMPT:-0}"
rm -rf "$WORK"; mkdir -p "$WORK/src" "$WORK/data" "$WORK/wheels" "$LOGS"; cd "$WORK" || exit 1
log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOGS/attempt_${ATTEMPT}.log"; }
push() {
    gcloud storage rsync -r "$WORK/src/results/analysis" "$RESULT_URI/analysis" --quiet 2>/dev/null
    gcloud storage rsync "$LOGS" "$RESULT_URI/logs" --quiet 2>/dev/null
}

log "setup: attempt $ATTEMPT on $(hostname), $(nproc) vCPU, $(free -g | awk '/Mem/ {print $2}') GB"
gcloud storage rsync "$RESULT_URI/logs" "$LOGS" --quiet 2>/dev/null
gcloud storage cp "$CODE_URI" code.tar.gz --quiet && tar xzf code.tar.gz -C src || { log "code fetch failed"; push; exit 2; }
gcloud storage rsync -r "$RESULT_URI/analysis" src/results/analysis --quiet 2>/dev/null  # resume
gcloud storage cp "$WHEELS_URI/*.whl" wheels/ --quiet || { log "wheel fetch failed"; push; exit 2; }
gcloud storage cp -r "$DATA_URI/*" data/ --quiet || { log "data fetch failed"; push; exit 2; }
log "data: $(du -sh data | cut -f1)"

PIP_WHEEL=$(ls wheels/pip-*.whl | head -1)
python3 -m venv --without-pip venv && venv/bin/python "$PIP_WHEEL/pip" install -q --no-index "$PIP_WHEEL" \
    && venv/bin/python -m pip install -q --no-index --find-links wheels "./src[plots]" || { log "install failed"; push; exit 5; }
PY="$WORK/venv/bin/python"
export IDS2EVAL_DATA="$WORK/data"
( while true; do { date -u +%FT%TZ; free -m; echo; } >> "$LOGS/memlog.txt"; sleep 30; done ) & MEM_PID=$!
( while true; do sleep 120; push; done ) & SYNC_PID=$!
cd src || exit 1

done_in() {  # done_in FILE KEY: KEY present at the top level of FILE
    $PY -c "import json,sys; sys.exit(0 if sys.argv[2] in json.load(open(sys.argv[1])) else 1)" "$1" "$2" 2>/dev/null
}
run() {
    log "run $1"; local start=$(date +%s); shift
    env PYTHONUNBUFFERED=1 "$@" >> "$LOGS/run.log" 2>&1; local s=$?
    log "exit $s after $(( $(date +%s) - start ))s"; push; return $s
}

status=0
run bot_host_holdout $PY validation/host_holdout.py bot-iot-official:2 || status=1
for name in cic-ids2018-fullscale cic-ddos2019-fullscale-main; do
    if done_in results/analysis/port_protocol_lookup.json "$name"; then log "skip $name (done)"; continue; fi
    run "port_protocol_$name" $PY validation/port_protocol_lookup_stream.py "$name" || status=1
done
kill $SYNC_PID $MEM_PID 2>/dev/null
push
log "finished with status $status"
exit $status
