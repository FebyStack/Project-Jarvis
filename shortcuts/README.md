# Jarvis Shortcut (iPhone)

It listens, sends what you said to Jarvis on the Mac over Tailscale, and speaks the answer. If Jarvis asks something back, the answer carries `"loop": "yes"` and the shortcut listens again; when the exchange is done, `loop` is absent and the shortcut stops.

You need: Tailscale signed in and **Connected** on the Mac and the iPhone (turn on *VPN On Demand* in the Tailscale app so it stays connected), `tailscale serve` running on the Mac, and the Mac's tailnet address, `https://<mac-name>.<tailnet>.ts.net` (`tailscale serve status` prints it).

## Get it onto the iPhone

1. On the Mac, open `shortcuts/Jarvis.shortcut` and choose **Add Shortcut**. It is the whole shortcut, signed, with the placeholder `PASTE_TOKEN_HERE` instead of the token. (Built by `spikes/06-phone/make_shortcut.py`; rebuild it if the Mac's address changes.)
2. Paste the token yourself; it is never shown in chat. On the Mac run `pbcopy < ~/.jarvis/token`, open the shortcut, click **›** on *Get contents of …/ask*, double-click `PASTE_TOKEN_HERE` under **Headers → Authorization** (it must read `Bearer ` then the token), press ⌘V. Then clear the clipboard: `pbcopy < /dev/null`.
3. Check the **If** step reads **If Dictionary Value does not have any value** (the value from *Get Value for loop*), with **Stop this shortcut** inside. If it shows *Condition* or a red warning, set it by clicking: *Condition* → **Select Variable** → the *Dictionary Value* chip under *Get Value for loop* → in its panel set *Type* **Text** → then choose **does not have any value**.
4. Send it to the iPhone: in Shortcuts on the Mac, right-click **Jarvis** → **Share** → **AirDrop** → your iPhone → **Add Shortcut**. (iCloud Sync also works if it is on in Shortcuts on both devices.) Never use **Copy iCloud Link**: that would publish the token.

## Start it

- **Back Tap** (what works): iPhone Settings → Accessibility → Touch → Back Tap → **Double Tap** → **Jarvis**. Double-tap the back of the phone and speak.
- Or tap its tile in Shortcuts, or add it to the home screen (long-press the tile → Share → Add to Home Screen).
- "Hey Siri, Jarvis" did **not** start it in testing (2026-11-14).

## Check it

- Wi-Fi off, mobile data on, Tailscale connected: double-tap the back, say something. You hear a reply within about 4 s.
- With the Mac server started as `server.py --ask-first`, the first reply is "Shall I go ahead?" and the shortcut listens again by itself.
- If you hear nothing and the Mac's `server.log` shows `401 shape: …`, the token in the header is wrong (the log line says how, never the value). "A server with the specified hostname could not be found" means Tailscale on the iPhone is off.

Tested 2026-11-14 on iOS (iPhone 12 Pro Max) and macOS 26.4 Shortcuts.
