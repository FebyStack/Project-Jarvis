#!/bin/bash
# Spike 5 Step 2: TextEdit snapshot/click/type, Finder drag. Scratch files only, cleaned up at the end.
# Run from the app that holds the Accessibility grant (Terminal). Don't touch mouse/keyboard while it runs.
# Optional: SHOT_DIR=<dir> also takes screenshots (needs Screen Recording). Logs go to tmp/logs/.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
SCR="$HERE/tmp/scratch"; LOGS="$HERE/tmp/logs"; TS=$(date +%Y%m%d-%H%M%S)
LOG="$LOGS/step2-$TS.log"; mkdir -p "$SCR" "$LOGS"
AD=agent-desktop

log() { echo "$(date +%H:%M:%S) $*" | tee -a "$LOG"; }
# run <label> <cmd...>: logs the command, its ok/error code, and keeps the JSON in $OUT
run() { local l=$1; shift; log "\$ $*"; OUT=$("$@" 2>&1); local ok; ok=$(jq -r 'if .ok then "ok" else "FAIL " + .error.code + ": " + .error.message end' <<<"$OUT" 2>/dev/null || echo "non-JSON: $OUT"); log "  $l -> $ok"; [ "$ok" = ok ]; }
# Window titles read back as the app name without Screen Recording, so find our window as the id that is new after `open`.
win_ids() { $AD list-windows --app "$1" 2>/dev/null | jq -r '.data[]? | select(.accessible) | .id' | sort; }
new_win() { # new_win <app> <ids before>: poll 15 s for a window id that was not there before
  local i id; for i in $(seq 30); do
    id=$(comm -13 <(echo "$2") <(win_ids "$1") | head -1); [ -n "$id" ] && { echo "$id"; return; }; sleep 0.5
  done; }
ref_where() { jq -r "[.. | objects | select(has(\"ref_id\") and ($1))][0].ref_id // empty" <<<"$2"; }
close_window() { # click the window's own Close button (no key presses: safe if the screen is locked)
  local app=$1 w=$2 ref
  ref=$($AD find --app "$app" --window-id "$w" --role button --name close --first | jq -r '[.. | objects | .ref_id? // empty][0] // empty')
  if [ -n "$ref" ]; then run "close $app window" $AD click "$ref"; else log "  no Close button found in $app $w"; fi
}

log "agent-desktop $($AD --version)  display: $(pmset -g log | grep -E 'Display is turned (on|off)' | tail -1 | cut -c1-60)  locked: $(ioreg -n Root -d1 | grep -o 'CGSSessionScreenIsLocked"=[A-Za-z]*' || echo no)"
AX=$($AD permissions | jq -r '.data.accessibility.state'); log "accessibility: $AX"
[ "$AX" = granted ] || { log "STOP: Accessibility not granted to the app running this script"; exit 1; }

# ── TextEdit: a fresh scratch file, so closing it never touches a real document ──
TE_WAS_RUNNING=$($AD list-apps --app TextEdit | jq '.data.apps | length')
DOC="$SCR/jarvis-scratch.txt"; : > "$DOC"
BEFORE=$(win_ids TextEdit); log "\$ open -a TextEdit $DOC"; open -a TextEdit "$DOC"
TW=$(new_win TextEdit "$BEFORE"); log "  TextEdit window: ${TW:-none}"
if [ -n "$TW" ] && run snapshot $AD snapshot --app TextEdit --window-id "$TW" -i --compact; then
  echo "$OUT" > "$LOGS/textedit-snapshot-$TS.json"
  TA=$(ref_where '.role|test("text";"i")' "$OUT"); log "  text area ref: ${TA:-none}"
  if [ -n "$TA" ]; then
    run "click (headless)" $AD click "$TA" || run "click (--headed)" $AD --headed click "$TA"
    LINE="Jarvis spike 5 typed this at $TS"
    run type $AD type "$TA" "$LINE"
    $AD get "$TA" --property value | jq -r '.data.value // .data.text // .data | tostring' | grep -qF "$LINE" \
      && log "  VERIFIED: line is in the document" || log "  NOT VERIFIED: line not read back"
    if [ -n "${SHOT_DIR:-}" ]; then
      run "screenshot window" $AD screenshot --window-id "$TW" "$SHOT_DIR/step4-window-$TS.png"
      run "screenshot screen 0" $AD screenshot --screen 0 "$SHOT_DIR/step4-screen-$TS.png"
    fi
  fi
  close_window TextEdit "$TW"   # file-backed doc: TextEdit autosaves into tmp/ and closes without a prompt
fi
[ "$TE_WAS_RUNNING" = 0 ] && run "quit TextEdit (we started it)" $AD close-app TextEdit

# ── Finder: drag tmp/scratch/src/jarvis-drag.txt onto tmp/scratch/src/dest (same window) ──
mkdir -p "$SCR/src/dest"; : > "$SCR/src/jarvis-drag.txt"
log "\$ open $SCR/src"; open "$SCR/src"
# Stage Manager reshuffles Finder's window list, so pick the window whose snapshot shows our file.
FW=""; for i in $(seq 15); do
  for w in $(win_ids Finder); do
    $AD snapshot --app Finder --window-id "$w" -i --compact 2>/dev/null | jq -e '[..|objects|select(.name?=="jarvis-drag.txt")]|length>0' >/dev/null && { FW=$w; break 2; }
  done; sleep 1; [ "$i" = 5 ] || [ "$i" = 10 ] && open "$SCR/src"   # list-windows sees only the active stage: re-activate
done; log "  Finder window: ${FW:-none}"
if [ -n "$FW" ] && run snapshot $AD snapshot --app Finder --window-id "$FW" -i --compact; then
  echo "$OUT" > "$LOGS/finder-snapshot-$TS.json"
  FROM=$(ref_where '(.name? // "")|test("^jarvis-drag")' "$OUT"); TO=$(ref_where '.name? == "dest"' "$OUT"); IV=$(ref_where '.role == "radiobutton" and .name? == "icon view"' "$OUT")
  log "  from: ${FROM:-none}  to: ${TO:-none}  icon-view button: ${IV:-none}"
  [ -n "$IV" ] && run "click 'icon view' (headless, already selected)" $AD click "$IV"
  # Default timing (drop-delay 500) reported ok without moving the file; 1 s pickup + 1 s hold works.
  [ -n "$FROM" ] && [ -n "$TO" ] && run drag $AD --headed drag --from "$FROM" --to "$TO" --duration 1000 --drop-delay 1000 --timeout-ms 10000
  [ -e "$SCR/src/dest/jarvis-drag.txt" ] && log "  VERIFIED: file moved into dest/" || log "  NOT VERIFIED: file still in src/"
  close_window Finder "$FW"
fi

rm -rf "$SCR"; log "cleaned up $SCR; log: $LOG"
