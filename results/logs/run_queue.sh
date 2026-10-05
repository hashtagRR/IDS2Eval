#!/bin/bash
cd /home/tango/projects/IDS2Eval
ulimit -v 22000000
while pgrep -f validation/matched_vs_novel.py >/dev/null; do sleep 30; done
echo "[queue] heldout start $(date -u +%H:%M)"
venv/bin/python3 -u validation/heldout_validation.py > /home/tango/projects/IDS2Eval_data/logs/heldout_validation.log 2>&1
echo "[queue] heldout exit $? $(date -u +%H:%M)"
venv/bin/python3 -u validation/model_sensitivity.py ton-iot-official:10 bot-iot-official:10 cic-ids2017-glf:5 > /home/tango/projects/IDS2Eval_data/logs/model_sensitivity.log 2>&1
echo "[queue] model_sensitivity exit $? $(date -u +%H:%M)"
