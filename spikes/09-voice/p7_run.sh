#!/bin/sh
# Reads the mic for 10 s from a temporary login agent (same python + WorkingDirectory as com.febriel.jarvisd).
REPO="$(cd "$(dirname "$0")/../.." && pwd)"; L=com.febriel.jarvis-probe7; D="$(mktemp -d)"; P="$D/$L.plist"
cat > "$P" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>$L</string>
<key>ProgramArguments</key><array><string>$REPO/.venv/bin/python</string><string>$REPO/spikes/09-voice/p7_mic.py</string></array>
<key>WorkingDirectory</key><string>$REPO</string>
<key>RunAtLoad</key><true/>
<key>StandardErrorPath</key><string>$HOME/.jarvis/probe-p7.err</string>
</dict></plist>
PL
rm -f "$HOME/.jarvis/probe-p7.log"
launchctl bootout gui/$(id -u)/$L 2>/dev/null
launchctl bootstrap gui/$(id -u) "$P" || exit 1
echo "Speak for 10 s. If macOS asks for Microphone access, grant it and re-run."
sleep 14
launchctl bootout gui/$(id -u)/$L 2>/dev/null; rm -rf "$D"
cat "$HOME/.jarvis/probe-p7.log" "$HOME/.jarvis/probe-p7.err" 2>/dev/null
echo "Also note which program System Settings > Privacy & Security > Microphone lists."
