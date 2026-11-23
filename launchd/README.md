# jarvisd login agent

`com.febriel.jarvisd.plist` starts `jarvis daemon` when you log in and restarts it if it stops. It sets no environment variables; the token lives in `~/.jarvis/token` and the log in `~/.jarvis/jarvisd.log`.

Load it (copies the file into your LaunchAgents folder, then starts it):

```bash
cp "/Users/febrielotud/Developer/Project Jarvis/launchd/com.febriel.jarvisd.plist" ~/Library/LaunchAgents/ && launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.febriel.jarvisd.plist
```

Unload it (stops jarvisd and keeps it from starting at login):

```bash
launchctl bootout gui/$(id -u)/com.febriel.jarvisd && rm ~/Library/LaunchAgents/com.febriel.jarvisd.plist
```

Stop any `jarvis daemon` you started by hand first: both want port 8787.

## Permissions

jarvisd needs two grants for the voice. macOS lists the program as **Python** (the interpreter behind `.venv/bin/jarvis`), not as jarvis or Terminal:

- **Microphone**: System Settings > Privacy & Security > Microphone, switch on "Python". Without it the mic gives only silence and `jarvis doctor` says jarvisd cannot hear.
- **Input Monitoring**: System Settings > Privacy & Security > Input Monitoring, switch on "Python". Without it the talk key (Right Option) is off and the HUD shows `MIC ● on, no key`; speaking the name still works.

The grants belong to the jarvisd process, not to the terminal you type in, so restart jarvisd after changing either:

```bash
launchctl kickstart -k gui/$(id -u)/com.febriel.jarvisd
```

Then check with `jarvis doctor`. A Python upgrade (uv-managed CPython, or Homebrew's) gives a new interpreter, and macOS can reset both grants; switch "Python" on again in both lists and restart.

## Speech models and offline use

`jarvis models` downloads the speech models once. jarvisd never downloads: it starts with `HF_HUB_OFFLINE=1` and loads them from the cache, so the voice works with no network. The login agent runs `.venv/bin/jarvis` directly and is unaffected by `uv`. By hand with no network, run `.venv/bin/jarvis …` or `uv run --frozen --no-sync jarvis …`: plain `uv run` tries to fetch the `en_core_web_sm` wheel again and fails.

## The face login agent

`com.febriel.jarvis-face.plist` starts `jarvis face` (the red circle and its agent beads) when you log in, and starts it again if it stops. It runs only in your desktop session, sets no environment variables, and needs no permission: no microphone, no Input Monitoring, no Accessibility. If it crashes, the traceback is in `~/.jarvis/face.log` (code lines only, never what you said or asked). It is a client of jarvisd like the terminal HUD; when jarvisd restarts or is not running yet, the circle goes grey with `NO DAEMON` and reconnects by itself every 2 seconds.

Load it:

```bash
cp "/Users/febrielotud/Developer/Project Jarvis/launchd/com.febriel.jarvis-face.plist" ~/Library/LaunchAgents/ && launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.febriel.jarvis-face.plist
```

Unload it (the circle goes away and does not come back at login):

```bash
launchctl bootout gui/$(id -u)/com.febriel.jarvis-face && rm ~/Library/LaunchAgents/com.febriel.jarvis-face.plist
```

Only one face runs at a time: a second `jarvis face` says so in one line on stderr and exits. While one you started by hand is up, the agent's copy says so once in `face.log`, waits, and takes over the moment yours quits. Because the agent keeps it alive, quitting the face's process brings it straight back; unload the agent to put it away.
