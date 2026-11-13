# Plan 1 spike findings

One section per spike: what was run, the numbers, pass or fail against the plan's bar, and what it means for the design.

## Spike 1 — Claude Code as the brain, on the subscription (Task 6)

Status (2026-11-10): **blocked at Step 1 — the standalone `claude` CLI is not logged in.** No bar could be measured yet. Not a design failure.

### What was run
- `spikes/01-brain/step1_stream.py`: starts `claude -p --model sonnet --input-format stream-json --output-format stream-json --verbose` as one child process and sends two user messages 60 s apart on stdin.
- `claude auth status` in a clean login-like environment (`env -i HOME USER PATH SHELL TERM`), inside and outside the tool sandbox.

### Results
| Check | Result |
|---|---|
| `ANTHROPIC_API_KEY` set? | No (asserted unset) |
| One process took both messages, same session id | Yes (one PID, one `session_id`, `system/init` emitted per turn) |
| `system/init` | `apiKeySource: "none"`, `model: claude-sonnet-5-5`, `claude_code_version: 2.1.312` |
| Both replies | `Failed to authenticate: OAuth session expired and could not be refreshed` |
| `claude auth status`, clean env | `loggedIn: false`, `authMethod: none` |
| Keychain item `Claude Code-credentials` | present (contents not read) |

### What it means
- The spec's constraint "Claude Code 2.1.312, logged in with a claude.ai subscription" holds for the **desktop app**, not the standalone CLI. The app authenticates its own sessions through the host (its child environment carries `CLAUDE_CODE_SDK_HAS_HOST_AUTH_REFRESH`, an `ANTHROPIC_BASE_URL` proxy, and `CLAUDE_CODE_SIMPLE`). A `jarvisd` started from launchd or Terminal will not have that; it needs the CLI's own subscription login.
- **Environment hygiene for Plan 2:** the desktop app's environment sets `CLAUDE_CODE_SIMPLE=1`, which is what `--bare` sets. `jarvisd` must start `claude` with a clean environment (no `CLAUDE_CODE_*`, no `ANTHROPIC_*`), never inherit one from a Claude session.
- 👤 **Needed from Febriel:** in Terminal, run `claude`, then `/login` and pick the claude.ai subscription (or `claude auth login`). Then `claude auth status` should show `loggedIn: true`. Steps 1–7 resume after that.

## Gate: open review findings

- **Fixed 2026-11-13 (was an allow-verdict bypass):** a `cd` behind a shell keyword was missed by the folder check, so `{ cd ~/Documents; } && rm a.txt` returned `allow`. Leading keywords are now skipped before the `cd` test. Regression test: `test_cd_after_a_keyword_still_poisons_relative_paths`. No findings open.
