# Jarvis Shortcut (iPhone)

Build this by hand in the Shortcuts app. It listens, sends what you said to Jarvis on the Mac over Tailscale, and speaks the answer. If Jarvis asks something back (`needs_reply: true`), it listens again.

Before you start you need: Tailscale signed in on the Mac and the iPhone, `tailscale serve` running on the Mac, and the Mac's tailnet HTTPS address. That address looks like `https://<mac-name>.<tailnet-name>.ts.net`. `tailscale serve status` on the Mac prints it.

## The token

You paste the token yourself; it is never shown in chat. On the Mac:

```bash
pbcopy < ~/.jarvis/token
```

With Handoff on, the iPhone can paste it (Universal Clipboard). When you are done, clear the Mac clipboard:

```bash
pbcopy < /dev/null
```

## Build it

New shortcut, named **Jarvis** (the name is what you say to Siri). Add these actions in order:

1. **Repeat**, set to **10** times. Shortcuts has no "repeat while" loop, so the loop runs at most 10 rounds and step 9 ends it early.
2. Inside Repeat: **Dictate Text**. Set *Stop Listening* to **After Pause** and *Language* to **English**.
3. **Get Contents of URL**:
   - URL: `https://<mac-name>.<tailnet-name>.ts.net/ask` (your address from above, plus `/ask`)
   - Tap **Show More**. *Method*: **POST**.
   - *Headers*: **Add new header**. Key `Authorization`, value `Bearer ` (with the space), then paste the token right after it.
   - *Request Body*: **JSON**. Add a **Text** field: key `text`, value the **Dictated Text** variable.
4. **Get Dictionary Value**: *Get* **Value** for key `say` in **Contents of URL**.
5. **Speak Text**: speak the **Dictionary Value** from step 4. Under Show More, turn on **Wait Until Finished** if it is there, so it does not listen while it is still talking.
6. **Get Dictionary Value**: *Get* **Value** for key `needs_reply` in **Contents of URL** (pick the variable from step 3, not step 4's output).
7. **If** the step 6 **Dictionary Value** *is* **false**:
8. inside the If: **Stop This Shortcut** (some versions list it as **Stop Shortcut**).
9. **End If**, then **End Repeat** (Shortcuts adds both).

If step 7 does not offer true/false for the value, set the condition to *is* **0** instead.

The first time it runs, Shortcuts asks to let "Jarvis" connect to your `ts.net` address. Choose **Always Allow**.

## Run it

- From the home screen: in the shortcut's menu choose **Add to Home Screen**.
- By voice: say "Hey Siri, Jarvis" (or "Siri, Jarvis"). Siri runs any shortcut when you say its name. If the phone is locked, Siri may ask you to unlock first.

## Check it

- Wi-Fi off, mobile data on: ask something. You should hear "You said: …" back.
- For the reply-loop test the Mac runs the server with `--ask-first`. The first answer ends "Shall I go ahead?", it listens again, and the second answer ends the shortcut.
- Remove the token from the header once and run it: Jarvis should refuse it (the request gets 401 and nothing is spoken). Put the token back.

Action names were checked on 2026-11-13 against Apple's Shortcuts User Guide (Repeat, Get Contents of URL, running shortcuts with Siri) and Matthew Cassinelli's action reference (Dictate Text, Get Dictionary Value, Get Contents of URL headers). Apple's guide did not confirm **Wait Until Finished** or **Stop This Shortcut**. Use whatever matching name your iOS version shows.
