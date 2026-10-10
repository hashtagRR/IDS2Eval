#!/usr/bin/env bash
# Cloud Batch runnable for the review-round-4 analyses:
#   1. validation/workflow_ablation_v2.py  (evidence and decision quality)
#   2. validation/flood_comparison.py      (Flood et al.'s released heuristics vs
#      IDS2Eval on ToN-IoT and UNSW-NB15; runs alone so its timings are fair)
#   3. validation/host_holdout_diag.py     (ToN-IoT and BoT-IoT host-holdout diagnostics)
# Each stage is skipped when its JSON already holds every requested dataset,
# so a spot preemption resumes. Inputs (environment): CODE_URI, WHEELS_URI,
# FLOOD_WHEELS_URI, FLOOD_SRC_URI (tar.gz of the tool's src/ and metadata/),
# DATA_URI (prefix with ton-iot-official/, bot-iot-official/, unsw-nb15/), RESULT_URI.
set -u
export PATH="${PATH:+$PATH:}/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export HOME="${HOME:-/root}"
WORK=/tmp/review4_task
LOGS="$WORK/logs"
ATTEMPT="${BATCH_TASK_RETRY_ATTEMPT:-0}"
rm -rf "$WORK"; mkdir -p "$WORK/src" "$WORK/data" "$WORK/wheels" "$WORK/flood_wheels" "$WORK/flood" "$LOGS"; cd "$WORK" || exit 1
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
gcloud storage cp "$FLOOD_WHEELS_URI/*.whl" flood_wheels/ --quiet || { log "flood wheel fetch failed"; push; exit 2; }
gcloud storage cp "$FLOOD_SRC_URI" flood.tar.gz --quiet && tar xzf flood.tar.gz -C flood || { log "flood fetch failed"; push; exit 2; }
gcloud storage cp -r "$DATA_URI/*" data/ --quiet || { log "data fetch failed"; push; exit 2; }
log "data: $(du -sh data | cut -f1)"

PIP_WHEEL=$(ls wheels/pip-*.whl | head -1)
python3 -m venv --without-pip venv && venv/bin/python "$PIP_WHEEL/pip" install -q --no-index "$PIP_WHEEL" \
    && venv/bin/python -m pip install -q --no-index --find-links wheels "./src[plots]" || { log "install failed"; push; exit 5; }
python3 -m venv --without-pip fvenv && fvenv/bin/python "$PIP_WHEEL/pip" install -q --no-index "$PIP_WHEEL" \
    && fvenv/bin/python -m pip install -q --no-index --find-links flood_wheels "numpy==1.25.2" "pandas==2.1.4" \
       "scikit-learn==1.3.2" "scipy==1.11.4" "matplotlib==3.8.0" "seaborn==0.13.1" "yellowbrick==1.4" setuptools \
    || { log "flood install failed"; push; exit 5; }
PY="$WORK/venv/bin/python"
log "$($PY -c 'import sklearn, pandas; print("ids2eval env: sklearn", sklearn.__version__, "pandas", pandas.__version__)'); $(fvenv/bin/python -c 'import sklearn, pandas, numpy; print("flood env: sklearn", sklearn.__version__, "pandas", pandas.__version__, "numpy", numpy.__version__)')"
export IDS2EVAL_DATA="$WORK/data" FLOOD_PY="$WORK/fvenv/bin/python"
( while true; do { date -u +%FT%TZ; free -m; echo; } >> "$LOGS/memlog.txt"; sleep 30; done ) & MEM_PID=$!
( while true; do sleep 120; push; done ) & SYNC_PID=$!
cd src || exit 1

has() {  # has FILE KEY...: every KEY present at the top level of FILE
    $PY -c "import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if all(k in d for k in sys.argv[2:]) else 1)" "$@" 2>/dev/null
}
run() {
    local name=$1; shift
    log "run $name"; local start=$(date +%s)
    env PYTHONUNBUFFERED=1 "$@" >> "$LOGS/$name.log" 2>&1; local s=$?
    log "$name exit $s after $(( $(date +%s) - start ))s"; push; return $s
}

status=0
if has results/analysis/workflow_ablation_v2.json summary; then log "skip workflow_ablation_v2 (done)"
else run workflow_ablation_v2 $PY validation/workflow_ablation_v2.py --jobs "$(nproc)" || status=1; fi
if has results/analysis/flood_comparison.json ton-iot-official unsw-nb15; then log "skip flood_comparison (done)"
else run flood_comparison $PY validation/flood_comparison.py "$WORK/flood" ton-iot-official unsw-nb15 || status=1; fi
if has results/analysis/host_holdout_diag.json ton-iot-official bot-iot-official; then log "skip host_holdout_diag (done)"
else run host_holdout_diag $PY validation/host_holdout_diag.py ton-iot-official bot-iot-official || status=1; fi
kill $SYNC_PID $MEM_PID 2>/dev/null
push
log "finished with status $status"
exit $status
