#!/usr/bin/env bash
# Cloud Batch runnable for validation/reuse_stratified.py (UNSW-NB15 and NSL-KDD,
# official partitions). Skips a dataset already in the result JSON, so a spot
# preemption resumes. Inputs (environment): CODE_URI, WHEELS_URI, DATA_URI
# (prefix with unsw-nb15/ and nsl-kdd/), RESULT_URI.
set -u
export PATH="${PATH:+$PATH:}/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export HOME="${HOME:-/root}"
WORK=/tmp/reuse_task
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
mkdir -p src/results/analysis
gcloud storage rsync -r "$RESULT_URI/analysis" src/results/analysis --quiet 2>/dev/null  # resume
gcloud storage cp "$WHEELS_URI/*.whl" wheels/ --quiet || { log "wheel fetch failed"; push; exit 2; }
for d in unsw-nb15 nsl-kdd; do
    gcloud storage cp -r "$DATA_URI/$d" data/ --quiet || { log "data fetch failed: $d"; push; exit 2; }
done
log "data: $(du -sh data | cut -f1)"
PIP_WHEEL=$(ls wheels/pip-*.whl | head -1)
python3 -m venv --without-pip venv && venv/bin/python "$PIP_WHEEL/pip" install -q --no-index "$PIP_WHEEL" \
    && venv/bin/python -m pip install -q --no-index --find-links wheels "./src[plots]" || { log "install failed"; push; exit 5; }
export IDS2EVAL_DATA="$WORK/data"
cd src || exit 1
log "run reuse_stratified"; start=$(date +%s)
env PYTHONUNBUFFERED=1 "$WORK/venv/bin/python" validation/reuse_stratified.py >> "$LOGS/reuse_stratified.log" 2>&1; s=$?
log "reuse_stratified exit $s after $(( $(date +%s) - start ))s"
push
exit $s
