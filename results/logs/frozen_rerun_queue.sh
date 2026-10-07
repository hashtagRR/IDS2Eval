#!/bin/bash
# Re-runs the local audits at the frozen code (paper-method-freeze + the
# result-identical feature_auc speed-up), one at a time.
cd /home/tango/projects/IDS2Eval_data || exit 1
LOG=/home/tango/projects/IDS2Eval/results/logs/frozen_rerun_queue.log
echo "[queue] code $(git -C /home/tango/projects/IDS2Eval rev-parse --short HEAD) start $(date -u +%FT%TZ)" >> $LOG
for ds in unsw-nb15 nsl-kdd ton-iot-official cic-ids2017; do
  echo "[queue] $ds start $(date -u +%T)" >> $LOG
  ( ulimit -v 9000000; /home/tango/projects/IDS2Eval/venv/bin/python3 run.py $ds ) >> $LOG 2>&1
  echo "[queue] $ds exit $? $(date -u +%T)" >> $LOG
done
echo "[queue] done $(date -u +%FT%TZ)" >> $LOG
