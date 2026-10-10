#!/usr/bin/env bash
# Cloud Batch runnable for the two synthetic studies added after review:
#   - validation/workflow_ablation.py (diagnostic / control / intervention)
#   - validation/homogeneity_coverage.py (interval coverage under repeated vectors)
# No dataset input. Each study is skipped when its JSON is already in
# RESULT_URI, so a spot preemption resumes. Inputs (environment): CODE_URI,
# WHEELS_URI, RESULT_URI.
set -u
export PATH="${PATH:+$PATH:}/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export HOME="${HOME:-/root}"
WORK=/tmp/synthetic_task
LOGS="$WORK/logs"
ATTEMPT="${BATCH_TASK_RETRY_ATTEMPT:-0}"
rm -rf "$WORK"; mkdir -p "$WORK/src/results/analysis" "$WORK/wheels" "$LOGS"; cd "$WORK" || exit 1
log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOGS/attempt_${ATTEMPT}.log"; }
push() {
    gcloud storage rsync -r "$WORK/src/results/analysis" "$RESULT_URI/analysis" --quiet 2>/dev/null
    gcloud storage rsync "$LOGS" "$RESULT_URI/logs" --quiet 2>/dev/null
}

log "setup: attempt $ATTEMPT on $(hostname), $(nproc) vCPU, $(free -g | awk '/Mem/ {print $2}') GB"
gcloud storage rsync "$RESULT_URI/logs" "$LOGS" --quiet 2>/dev/null
gcloud storage cp "$CODE_URI" code.tar.gz --quiet && tar xzf code.tar.gz -C src || { log "code fetch failed"; push; exit 2; }
mkdir -p src/results/analysis
gcloud storage rsync -r "$RESULT_URI/analysis" src/results/analysis --quiet 2>/dev/null  # resume
gcloud storage cp "$WHEELS_URI/*.whl" wheels/ --quiet || { log "wheel fetch failed"; push; exit 2; }
PIP_WHEEL=$(ls wheels/pip-*.whl | head -1)
python3 -m venv --without-pip venv && venv/bin/python "$PIP_WHEEL/pip" install -q --no-index "$PIP_WHEEL" \
    && venv/bin/python -m pip install -q --no-index --find-links wheels ./src || { log "install failed"; push; exit 5; }
PY="$WORK/venv/bin/python"
( while true; do sleep 120; push; done ) & SYNC_PID=$!
cd src || exit 1

status=0
for study in workflow_ablation homogeneity_coverage; do
    if [ -s "results/analysis/$study.json" ]; then log "skip $study (done)"; continue; fi
    log "run $study"; start=$(date +%s)
    env PYTHONUNBUFFERED=1 $PY "validation/$study.py" --jobs "$(nproc)" >> "$LOGS/$study.log" 2>&1; s=$?
    log "$study exit $s after $(( $(date +%s) - start ))s"; push
    [ $s -eq 0 ] || status=1
done
kill $SYNC_PID 2>/dev/null
push
log "finished with status $status"
exit $status
