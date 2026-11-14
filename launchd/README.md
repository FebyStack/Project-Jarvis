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
