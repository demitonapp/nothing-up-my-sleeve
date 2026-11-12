# The fleet — handover, 12 November 2026

This is the state to pick up from when the chat is archived. It covers what was built, what is
running, what is waiting on a person, and the commands that bring it all back.

## The pages

Both addresses serve the same Liberty Machine (the site is mid-rename; neither is a dead end):

- `http://localhost:4321/orbitals/demiton/liberty-machine/operations`
- `http://localhost:4321/liberty-machine/operations` (alias)

| Drone | Page | State at handover |
|---|---|---|
| **D1 Browser** | `.../operations/browser` | Fara1.5-9B and 4B installed; signed-in Chrome profile; four test sites |
| **D2 Email** | `.../operations/email` | Mailbox setup ready; **0 accounts connected**; Microsoft client id not set |
| **D3 Phone** | `.../operations/phone` | Local test line works; PersonaPlex live voice running |

## What is done

- **Research report** on sub-10B browser agents:
  `research_notes/Fara MolmoWeb Holo browser agents/sub-10b-browser-agent-comparison.md`.
- **D1 Browser drone**: Fara1.5-9B (Q4_K_M + mmproj, 6.8 GB) and Fara1.5-4B in `data/models/`;
  model selection; live run with screenshot, step log and answer; `browser_task` /
  `browser_task_status` chat tools. Verified on example.com, Hacker News and a local button page.
- **Browser test bench**: a dedicated signed-in Chrome profile at `data/browser-profile` (CDP 9333),
  `open sign-in` / `check` / `run test` for LinkedIn, X, Google Analytics and Search, and a
  "use the signed-in Chrome profile" toggle on the task form.
- **D2 Email drone**: card + art, text pilots (Qwen3.5 9B/4B), and a mailbox manager that supports
  Google App Passwords, Proton Mail Bridge and Microsoft device-code OAuth. Every save is tested
  against IMAP and SMTP; secrets stay in `data/email-secrets.json` (0600) and never return to the page.
- **D3 Phone drone**: card + art, local test line (typed person, Qwen3.5 4B pilot, macOS `say`),
  transcript, hang-up, safety terms; `phone_call` / `phone_say` / `phone_end` chat tools.
- **PersonaPlex live voice**: the MLX Q4 build (`data/models/personaplex-edge-q4`, 5.24 GiB) runs at
  `127.0.0.1:8998`, embedded in the phone page. A real session measured ~985 ms end-to-end, RTF 1.11,
  0 underruns.
- **The page order** the user asked for: the fleet cards are the first thing on Operations.
- **50 targeted tests** (drones, chat tools, chat, labs), `tsc` and ruff; the production build
  includes both address variants. The full suite still has slow network-dependent tests in this
  environment; the ledger's Postgres type cast found by it was fixed.

## What is waiting on a person

1. **Connect a mailbox.** 0 accounts are configured. Google is the quickest (App Password);
   Proton needs Bridge running; Microsoft needs a one-time app registration (client id + device sign-in).
2. **Sign in to LinkedIn and X (and Google Analytics) once** in the Chrome window opened by
   `open sign-in`, then press `check`. Chrome is already open on the dedicated profile.
3. **Run the four test presets.** The plumbing is proven, but Fara1.5-9B's success on the signed-in
   sites is not yet demonstrated consistently; the presets are ordinary goals that can be tuned.

## What is deliberately not built

- The email drone does not read, draft or send yet (mailbox configuration only).
- No PSTN telephony: the phone drone is local test line only, as chosen.
- PersonaPlex's live audio is not merged into the typed transcript or the phone safety gates; it is
  its own embedded UI.

## Run it again

```bash
# API (8787) and dashboard (4321)
cd ~/Source/Thorp
nohup backend/.venv/bin/thorp dash > /tmp/thorp-dash.log 2>&1 &
nohup pnpm --dir frontend dev > /tmp/thorp-frontend.log 2>&1 &

# PersonaPlex live voice (only if the phone page says stopped)
cd data/models/personaplex-edge-q4
.venv/bin/personaplex-edge serve --artifact . --host 127.0.0.1 --port 8998 --metrics-dir outputs/live
```

Chrome for the signed-in profile is opened by the browser page's `open signed-in Chrome`; it runs with
`--no-sandbox --disable-gpu` because the harness sandbox blocks Chrome's own sandbox and GPU process.

## Licences and cautions

- **Fara1.5** — MIT. The GGUF build is a Q4 quantisation of `microsoft/Fara1.5-9B`.
- **PersonaPlex** — the official `nvidia/personaplex-7b-v1` is gated and CUDA-first; the connected build
  is the community MLX Q4 conversion `Investigo/personaplex-edge-q4`, licensed **CC BY-NC 4.0 +
  NVIDIA Open Model License (non-commercial)**.
- PersonaPlex allows **one session at a time**; after an aborted session, stop and start it in the
  panel to clear the lock.
- `data/` (models, profiles, secrets, run history) is gitignored; it is not in the repository.
