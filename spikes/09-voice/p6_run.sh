#!/bin/sh
# Starts p6_tap.py as a temporary login agent (same python + WorkingDirectory as com.febriel.jarvisd), 30 s, then removes it.
REPO="$(cd "$(dirname "$0")/../.." && pwd)"; L=com.febriel.jarvis-probe; D="$(mktemp -d)"; P="$D/$L.plist"
cat > "$P" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>$L</string>
<key>ProgramArguments</key><array><string>$REPO/.venv/bin/python</string><string>$REPO/spikes/09-voice/p6_tap.py</string></array>
<key>WorkingDirectory</key><string>$REPO</string>
<key>RunAtLoad</key><true/>
<key>StandardErrorPath</key><string>$HOME/.jarvis/probe-p6.err</string>
</dict></plist>
PL
launchctl bootout gui/$(id -u)/$L 2>/dev/null
launchctl bootstrap gui/$(id -u) "$P" || exit 1
echo "NOW (30 s): press and release Right Option, then Option+E, then type a few keys. If macOS asks for Input Monitoring, grant it and re-run."
sleep 32
launchctl bootout gui/$(id -u)/$L 2>/dev/null; rm -rf "$D"
cat "$HOME/.jarvis/probe-p6.log"; cat "$HOME/.jarvis/probe-p6.err" 2>/dev/null
echo "Also note which program System Settings > Privacy & Security > Input Monitoring lists (python / Python / jarvis)."
