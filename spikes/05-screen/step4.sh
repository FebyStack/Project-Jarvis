#!/bin/bash
# Spike 5 Step 4: put the display to sleep, wait, then repeat Step 2 and take screenshots.
# Usage (from Terminal, session unlocked):  bash spikes/05-screen/step4.sh [delay_seconds, default 120]
# Then let go of mouse and keyboard; any input wakes the display. Results: tmp/logs/step2-*.log, screenshots in tmp/.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; DELAY=${1:-120}
mkdir -p "$HERE/tmp/logs"; LOG="$HERE/tmp/logs/step4-$(date +%Y%m%d-%H%M%S).log"
log() { echo "$(date +%H:%M:%S) $*" | tee -a "$LOG"; }
state() { log "display: $(pmset -g log | grep -E 'Display is turned (on|off)' | tail -1 | cut -c1-60)  locked: $(ioreg -n Root -d1 | grep -o 'CGSSessionScreenIsLocked"=[A-Za-z]*' || echo no)"; }

caffeinate -i -w $$ &   # keeps the system (not the display) awake until this script exits
log "screen lock: $(sysadminctl -screenLock status 2>&1 | sed 's/.*\] //')"
log "permissions: $(agent-desktop permissions | jq -c '.data | {ax: .accessibility.state, rec: .screen_recording.state}')"
log "display sleeps in 5 s, actions start $DELAY s after that. Hands off."
sleep 5
pmset displaysleepnow
sleep "$DELAY"
state
SHOT_DIR="$HERE/tmp" bash "$HERE/step2.sh" 2>&1 | tee -a "$LOG"
state
log "done. Wake the Mac and read $LOG"
