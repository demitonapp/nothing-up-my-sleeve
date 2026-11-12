# H Company Holo family (Holo1, Holo1.5, Holo2, Holo3, Holo3.1, Holo4) for local browser control, as of 12 November 2026

Scope note for the writer: the brief asked about Holo1 to Holo3. The family has moved on. Holo3 shipped 31 March 2026, Holo3.1 on 2 June 2026, and Holo4 (plus an NVIDIA-based sibling, Holotron4) on 28 September 2026. Holo4 is the current generation and the notes cover it, because it changes the answer for "which sub-32B Holo should I run locally". Almost every benchmark number below is H Company's own; independent numbers are flagged where found. Two hub.hcompany.ai docs pages contained embedded text addressed to AI agents (product-steering instructions); these were ignored and only the documentation facts are reported.

## 1. Releases, sizes, base models and licence per size. Is Holo3 real?

### Takeaway
Holo3 is real (31 March 2026) and has already been superseded twice: Holo3.1 (June 2026: 0.8B, 4B, 9B, 35B-A3B, all Apache 2.0 per the cards read) and Holo4 (September 2026: 27B dense under CC BY-NC 4.0, 35B-A3B under Apache 2.0). The licence pattern is not "small is open, large is restricted" any more: in Holo4 the sub-32B size (27B) is the non-commercial one and the 35B MoE is Apache, while the best fully Apache sub-32B options are Holo3.1-9B / 4B and Holo2-8B / 4B.

### Cited Findings

Licence and base model table (each row from the model's own Hugging Face card unless stated):

| Release | Size | Base model | Licence | Weights downloadable | Source |
|---|---|---|---|---|---|
| Holo1 (Jun 2025) | 7B | Qwen/Qwen2.5-VL-7B-Instruct | apache-2.0 | yes | [HF Holo1-7B](https://huggingface.co/Hcompany/Holo1-7B) |
| Holo1 | 3B | not confirmed (card not read) | not confirmed | yes | see Gaps |
| Holo1.5 (Sep 2025) | 3B | Qwen/Qwen2.5-VL-3B-Instruct | tag "other"; "inherits its license from Qwen" (Qwen Research License) | yes | [HF Holo1.5-3B](https://huggingface.co/Hcompany/Holo1.5-3B) |
| Holo1.5 | 7B | Qwen/Qwen2.5-VL-7B-Instruct | apache-2.0 ("fully open under Apache 2.0") | yes | [HF Holo1.5-7B](https://huggingface.co/Hcompany/Holo1.5-7B) |
| Holo1.5 | 72B | not named on the 7B card | "research-only license (non-commercial)"; commercial use by contacting H | yes | [HF Holo1.5-7B](https://huggingface.co/Hcompany/Holo1.5-7B) |
| Holo2 (late 2025) | 4B | Qwen/Qwen3-VL-4B-Thinking | apache-2.0 | yes | [HF Holo2-4B](https://huggingface.co/Hcompany/Holo2-4B) |
| Holo2 | 8B | not read directly (Qwen3-VL-8B-Thinking is the baseline row in H's tables) | Apache 2.0 per the 30B card and H hub | yes | [HF Holo2-30B-A3B](https://huggingface.co/Hcompany/Holo2-30B-A3B) |
| Holo2 | 30B-A3B | Qwen/Qwen3-VL-30B-A3B-Thinking | cc-by-nc-4.0 (research-only, non-commercial) | yes | [HF Holo2-30B-A3B](https://huggingface.co/Hcompany/Holo2-30B-A3B) |
| Holo3 (31 Mar 2026) | 35B-A3B | Qwen/Qwen3.5-35B-A3B | apache-2.0 | yes | [HF Holo3-35B-A3B](https://huggingface.co/Hcompany/Holo3-35B-A3B) |
| Holo3 | 122B-A10B | not stated | API only per H's page (weights not offered) | no evidence of weights | [hcompany.ai/holo3](https://hcompany.ai/holo3) |
| Holo3.1 (2 Jun 2026) | 0.8B | Qwen 3.5 family | Apache 2.0 | yes | [H hub local inference](https://hub.hcompany.ai/agents-api/local-inference.md) |
| Holo3.1 | 4B (hub metadata says 5B params) | Qwen 3.5 family | apache-2.0 | yes | [HF Holo-3.1-4B](https://huggingface.co/Hcompany/Holo-3.1-4B) |
| Holo3.1 | 9B | Qwen 3.5 family | apache-2.0 | yes | [HF Holo-3.1-9B](https://huggingface.co/Hcompany/Holo-3.1-9B) |
| Holo3.1 | 35B-A3B | Qwen 3.5 family | Apache 2.0 stated once for the family on the 4B and 9B cards; the 35B card itself was not read | yes (BF16, FP8, NVFP4, Q4 GGUF) | [HF Holo-3.1-9B](https://huggingface.co/Hcompany/Holo-3.1-9B) |
| Holo4 (28 Sep 2026) | 27B dense | Qwen/Qwen3.8-27B | cc-by-nc-4.0 ("Non-commercial (CC BY-NC 4.0)") | yes (BF16, FP8, NVFP4, Q4 GGUF) | [HF Holo4-27B](https://huggingface.co/Hcompany/Holo4-27B) |
| Holo4 | 35B-A3B MoE | Qwen/Qwen3.6-35B-A3B | Apache 2.0 | yes (BF16, FP8, NVFP4, Q4 GGUF) | [HF Holo4-35B-A3B](https://huggingface.co/Hcompany/Holo4-35B-A3B) |
| Holotron4 (28 Sep 2026) | 30B-A3B (33B params in metadata) | NVIDIA Nemotron 3 Nano Omni | nvidia-open-model-agreement | yes (BF16, FP8 only) | [HF Holotron4-30B-A3B](https://huggingface.co/Hcompany/Holotron4-30B-A3B) |

- Holo3 was released on 31 March 2026; the 35B-A3B weights are on Hugging Face under Apache 2.0 and also served on H's inference API with a free tier; the 122B-A10B (122B total, 10B active) is offered through the inference API — [hcompany.ai/holo3](https://hcompany.ai/holo3)
- Holo3.1 was published 2 June 2026 in four sizes (0.8B, 4B, 9B, 35B-A3B), "based on the Qwen family", with FP8, Q4 GGUF and NVFP4 quantised checkpoints for the 35B-A3B — [HF blog: Holo3.1](https://huggingface.co/blog/hcompany/holo31)
- Holo4 was published 28 September 2026: Holo4-27B (dense), Holo4-35B-A3B (MoE) and Holotron4 Nano built on NVIDIA Nemotron 3 Nano Omni; weights in BF16, FP8, NVFP4 and 4-bit GGUF, also on the H Models API — [HF blog: Holo4](https://huggingface.co/blog/Hcompany/holo4)
- H's own local-inference doc summarises licences as: Holo4 35B-A3B Apache 2.0; Holo4 27B CC BY-NC 4.0, research use; Holo3.1 9B, 4B, 0.8B Apache 2.0 — [H hub local inference](https://hub.hcompany.ai/agents-api/local-inference.md)
- The Holo2-30B-A3B card is internally inconsistent: header tag cc-by-nc-4.0 and body "research-only", but a later generic line reads "License: Apache 2.0 License" — [HF Holo2-30B-A3B](https://huggingface.co/Hcompany/Holo2-30B-A3B)
- The Hcompany org page on 12 Nov 2026 surfaces only Holo4 / Holotron4 repos, NeoMME encoders, four datasets (h_cua_perf, trajectories, DragOn, WebClick) and four Holo1 / Holo1.5 Spaces, three of which show "Build error" and one "Paused"; older model repos still resolve by direct URL — [HF Hcompany org](https://huggingface.co/Hcompany)
- A Holo2-235B-A22B "preview" also exists as a research release focused on UI localisation (seen only as a search-result title; page not read, unverified) — [HF blog: Holo2-235B-A22B](https://huggingface.co/blog/Hcompany/introducing-holo2-235b-a22b)

### Inferences
- For a strictly sub-32B, permissively licensed local model the candidates are Holo3.1-9B, Holo3.1-4B, Holo3.1-0.8B, Holo2-8B, Holo2-4B, Holo1.5-7B and Holo1-7B (all Apache 2.0). Holo4-27B is sub-32B and the strongest, but CC BY-NC 4.0. For a non-commercial open-source project that only uses the weights (does not vendor or sell them), NC may be acceptable, but that is a licence judgement for the user.
- Holo3-35B-A3B, Holo3.1-35B-A3B and Holo4-35B-A3B sit just above a 32B total-parameter line but activate only about 3B parameters per token; all 35B must still be resident in memory (a Q4 GGUF is 21.3 GB). Whether they count as "sub-32B" depends on whether the limit is about memory or about compute.
- H Company's restricted tier has moved around between generations (72B research-only in 1.5, 30B-A3B NC in Holo2, 122B API-only in Holo3, 27B NC in Holo4), so licence must be checked per repo, never assumed from size.

### Gaps
- Holo1-3B card not read; its licence and base (presumably Qwen2.5-VL-3B-Instruct with the Qwen Research License, as for Holo1.5-3B) are unconfirmed.
- Holo2-8B card and Holo-3.1-35B-A3B card were not read directly; their licences are taken from sibling cards and H's hub doc.
- Exact Holo2 release date not confirmed from a primary source (card citation says only year 2025).
- hub.hcompany.ai/models/comparingmodels and hub.hcompany.ai/changelog/holomodels (the suggested comparison and changelog pages) return HTTP 404 as of 12 Nov 2026; the hub now has a "List models" API page ("served models, limits, pricing, and deprecation dates") that was not read, so current API prices and deprecation dates for older Holo models are unknown.

## 2. Grounding model or full agent policy? What must be added? Surfer-H and Surfer 2

### Takeaway
The family evolved from a localiser into an end-to-end policy. Holo1 was a component of Surfer-H; Holo1.5 is a localisation and UI question-answering model that needs a separate planner; Holo2 added navigation policy; Holo3, 3.1 and 4 are presented as single-model computer-use agents that still need a harness (H's MIT-licensed `hai-agents` SDK / `holo` CLI, or any OpenAI-compatible agent loop). Surfer-H's CLI was open (BSD-3) but is archived and deprecated; no released code was found for Surfer 2.

### Cited Findings
- Holo1 is "an Action Vision-Language Model (VLM) developed by HCompany for use in the Surfer-H web agent system"; Surfer-H has three independent modules (policy, localizer, validator), and Holo1 can fill any of them, with a different model allowed per module — [HF Holo1-7B](https://huggingface.co/Hcompany/Holo1-7B)
- Holo1.5 is a "VLM for Computer Use agents" that excels at "UI localization and UI-based question answering"; the card describes the models as foundations for agents "like Surfer-H" and does not describe an agent policy — [HF Holo1.5-7B](https://huggingface.co/Hcompany/Holo1.5-7B)
- Holo2 is described as models for "navigation and computer use agents" covering web, desktop and mobile, improving "policy learning, action grounding, and cross-environment generalisation" over Holo1.5; trained by supervised fine-tuning then online RL (GRPO) — [HF Holo2-30B-A3B](https://huggingface.co/Hcompany/Holo2-30B-A3B)
- Holo4 is used "with the hai-agents harness", which sends screenshots and tool results to the model and executes its requested clicks, typing, code and tool calls — [HF Holo4-35B-A3B](https://huggingface.co/Hcompany/Holo4-35B-A3B)
- A community project runs Holo3.1-4B as the only GUI model, "planning, action selection, and on-screen target location in one model", with "no separate planner" — [GitHub xmasdev/local-cua](https://github.com/xmasdev/local-cua)
- `hcompai/hai-agents-python` is the "Python SDK for H Company's Agents API", MIT licensed, ships a `holo` CLI, runs agents on H's hosted infrastructure by default with local execution supported, and names agents `h/web-surfer-pro`, `h/web-surfer-flash` and `h/holo-desktop`; 46 stars, 4 open issues, 194 commits when read — [GitHub hcompai/hai-agents-python](https://github.com/hcompai/hai-agents-python)
- H's docs describe a local runtime ("Run the agent loop on your machine with Client.local(), on H's hosted model or your own Holo4 server") and local inference ("Serve open-weight Holo4 or Holo3.1 with llama.cpp or vLLM and point base_url at it") — [H hub docs index](https://hub.hcompany.ai/llms.txt)
- `hcompai/surfer-h-cli` (the CLI for running Surfer-H, BSD-3-Clause, 163 stars) is archived and read-only: "Surfer-H-CLI has been deprecated and is no longer maintained"; H points users to its Models API, Agent API and `hai-agents`. Its scripts took OpenAI-compatible endpoints for policy and localizer, and one variant (`run-on-holo-val-gpt41.sh`) used GPT-4.1 as validator — [GitHub hcompai/surfer-h-cli](https://github.com/hcompai/surfer-h-cli)
- Surfer 2 (arXiv 2510.19949, 22 Oct 2025, 55 authors) is "a unified architecture operating purely from visual observations" with hierarchical context management, decoupled planning and execution, and self-verification; the arXiv page links no code repository — [arXiv 2510.19949](https://arxiv.org/abs/2510.19949)
- In Surfer 2 the core reasoning relied on general-purpose frontier models (OpenAI o3, GPT-4.1, Anthropic Claude Sonnet 4.5) and the localizer was Holo1.5 (7B and 72B) — [alphaXiv overview of 2510.19949](https://www.alphaxiv.org/overview/2510.19949) (secondary summary of the paper; unverified against the PDF)
- H's product line as of Nov 2026: an Agents API (managed computer-use agents), a Models API (OpenAI-compatible Holo models) and HoloTab (a free Chrome extension) — [H hub quickstart](https://hub.hcompany.ai/quickstart)

### Inferences
- For a local browser agent the minimum stack is: a Holo3.1 or Holo4 model served via llama.cpp or vLLM, plus a loop that screenshots, calls the model and executes actions. H's own loop is the `hai-agents` local runtime; the open question (see Gaps) is how much of that loop works without an H account.
- Holo1 and Holo1.5 should not be chosen as a standalone browser agent in 2026: Holo1.5 scored 5.8 to 6.4% on OSWorld as a navigator in H's own table (section 4) and its reference harness is deprecated.

### Gaps
- Whether Surfer 2's code was ever released was not established; no repository was found.
- Not confirmed whether the `hai-agents` local runtime contains the full agent loop in the MIT repo or still calls H's platform for orchestration.
- Per-module model assignment for the Surfer-H 92.2% WebVoyager headline (which model was validator) was not confirmed from the paper body; only the abstract and model card were read.

## 3. Inputs, outputs, action space, platforms, and attaching to the user's own Chrome

### Takeaway
Holo models are screenshot-only (no DOM or accessibility tree in any primary source) and emit coordinate actions, as absolute pixels in Holo1 and reportedly 0 to 1000 normalised values with native function calling in Holo3.1. Web, desktop and mobile are all claimed from Holo2 onward. H's harness can drive Chrome on the user's machine over remote debugging, but it deliberately uses a dedicated profile (`~/.hai/chrome-profile`), not the everyday profile; you sign in once inside that profile.

### Cited Findings
- Holo1 takes the screenshot at native size after a `smart_resize`, and outputs absolute pixel coordinates, for example `Click(352, 348)` or structured `ClickAction(action='click', x=352, y=340)`; the card warns the image must be resized to match because coordinates are absolute — [HF Holo1-7B](https://huggingface.co/Hcompany/Holo1-7B)
- Holo2 targets "multi-domain GUI Agents" across web, desktop and mobile — [HF Holo2-30B-A3B](https://huggingface.co/Hcompany/Holo2-30B-A3B)
- Holo3.1 supports structured JSON outputs (from Holo3) and adds native function-calling; H says the two modes reach near-parity on OSWorld and an internal suite — [HF blog: Holo3.1](https://huggingface.co/blog/hcompany/holo31)
- A community implementer reports H's published Holo3.1 conventions as function calling, `<observation>` screenshots and coordinates on a 0 to 1000 scale (example `click(element="Subject field", x=668, y=507)`) — [GitHub xmasdev/local-cua](https://github.com/xmasdev/local-cua)
- Holo4 works through "graphical interface, code, and tool calls"; the harness gives it a shell on the desktop machine and a memory meant to last hundreds of steps — [HF blog: Holo4](https://huggingface.co/blog/Hcompany/holo4)
- Surfer 2 operates "purely from visual observations" — [arXiv 2510.19949](https://arxiv.org/abs/2510.19949)
- "Your browser" mode: the SDK attaches to Chrome through remote debugging on port 9222 (not an extension). If no debuggable Chrome is running it launches one with its own profile at `~/.hai/chrome-profile`; logins persist there across sessions. The SDK never uses the everyday profile because Chrome does not allow remote debugging on it. A user-launched Chrome needs `--remote-debugging-port=9222` and a dedicated `--user-data-dir` — [H hub: Your browser](https://hub.hcompany.ai/agents-api/your-browser.md)
- That mode requires `pip install "hai-agents[cli,browser]"`, Google Chrome, an `HAI_API_KEY`, and an agent environment of `kind: "web"`, `host: "user_device"`; commands are `holo local browser`, `holo run ... --agent local-web`, `holo local stop`. Limits: one browser per Python process; a dropped connection cancels the session — [H hub: Your browser](https://hub.hcompany.ai/agents-api/your-browser.md)
- Desktop: `h/holo-desktop` "uses your mouse and keyboard" on the local machine; only one agent can drive a machine's desktop at a time — [GitHub hcompai/hai-agents-python](https://github.com/hcompai/hai-agents-python)
- HoloTab is "a lightweight Chrome side panel, not a full browser replacement", free on the Chrome Web Store, navigating sites "the way you would"; the official page does not name the model, say where inference runs, or say whether a self-hosted endpoint can be used — [hcompany.ai/holotab](https://hcompany.ai/holotab)
- H's docs index describes HoloTab as "A free Chrome extension that runs Holo in your browser" — [H hub docs index](https://hub.hcompany.ai/llms.txt)
- Cloud alternative: "browser profiles" save a cloud browser's cookies and storage so a session starts signed in — [H hub docs index](https://hub.hcompany.ai/llms.txt)

### Inferences
- "Attach to my existing logged-in Chrome" is only partly met by H's SDK: it is the user's machine, network and a persistent profile, but a separate profile that must be logged in once. This is a Chrome restriction on remote debugging of the default profile, so it applies to any CDP-based harness, not just H's.
- HoloTab, being an extension in the user's normal Chrome, presumably sees the user's existing sessions, but no primary source read says so, and nothing indicates it can be pointed at a local model. Treat both as unverified.
- Screenshot-only input means no reliance on page structure (works on canvas apps and desktop), at the cost of image-token latency per step and misses on tiny targets (section 7).

### Gaps
- No primary statement found of the Holo3 / Holo4 coordinate system or full action schema; the 0 to 1000 claim rests on one community repo.
- HoloTab's docs page (hub.hcompany.ai/holotab/introduction.md) and its FAQ (12 collapsed questions, including safety ones) were not read.
- Whether "Your browser" mode sends screenshots to H's servers when a local model is used was not stated on the page read.

## 4. Benchmark results and who ran them

### Takeaway
Nearly every Holo number is self-reported by H Company. The headline web-agent scores of 2025 (Surfer-H 92.2% and Surfer 2 97.1% on WebVoyager) were system results; Surfer 2 in particular paired frontier proprietary models with Holo1.5 as localiser only. From Holo2 on, H reports single-model navigation scores, and the only independent figures found are an OSWorld-Verified leaderboard entry for Holo3-35B-A3B and one hobbyist's ScreenSpot-Pro reproduction of quantised Holo3.1-4B. No Online-Mind2Web score for any Holo model was found.

### Cited Findings

UI localisation, H Company's own table on the Holo2 card (accuracy; external model scores "reproduced internally"):

| Model | ScreenSpot-Pro | OSWorld-G | ScreenSpot-v2 | WebClick-v1 |
|---|---|---|---|---|
| Holo2-30B-A3B | 66.1 | 76.1 | 94.9 | 91.3 |
| Holo2-8B | 58.9 | 70.1 | 93.2 | 89.5 |
| Holo2-4B | 57.2 | 69.4 | 93.2 | 88.8 |
| Holo1.5-72B | 63.3 | 71.8 | 94.4 | 92.4 |
| Holo1.5-7B | 57.9 | 66.2 | 93.3 | 90.2 |
| Holo1.5-3B | 51.4 | 61.5 | 91.6 | 81.4 |
| Qwen3-VL-8B-Thinking (base) | 38.5 | 56.0 | 91.5 | 85.9 |
| UI-TARS-1.5-7B | 39.0 | 61.0 | 94.0 | 86.1 |

— [HF Holo2-30B-A3B](https://huggingface.co/Hcompany/Holo2-30B-A3B); the Holo1.5 card gives the same Holo1.5 figures to two decimals (7B: ScreenSpot-v2 93.31, ScreenSpot-Pro 57.94, OSWorld-G 66.27) — [HF Holo1.5-7B](https://huggingface.co/Hcompany/Holo1.5-7B)

Navigation as a single model, H Company's own table on the Holo2 card (success rate):

| Model | WebVoyager | WebArena | OSWorld | AndroidWorld |
|---|---|---|---|---|
| Holo2-30B-A3B | 83.0 | 46.3 | 37.4 | 71.6 |
| Holo2-8B | 80.2 | 42.2 | 39.9 | 60.4 |
| Holo2-4B | 80.2 | 41.0 | 37.7 | 64.6 |
| Holo1.5-7B | 65.9 | 23.4 | 6.4 | 32.7 |
| Holo1.5-3B | 56.1 | 15.4 | 5.8 | 27.5 |
| Qwen3-VL-8B-Thinking (base) | 72.0 | 31.9 | 28.8 | 52.6 |

— [HF Holo2-30B-A3B](https://huggingface.co/Hcompany/Holo2-30B-A3B). The card says bold values "will denote state-of-the-art once final evaluations are available" and that external scores were "reproduced internally in the Surfer 2 agent".

- Holo1 on WebVoyager (643 tasks), H's own: Surfer-H + Holo1-7B 92.2% at $0.13 per task; Surfer-H + Holo1-3B 89.7% at $0.11; Surfer-H + GPT-4.1 92.0% at $0.54; Surfer-H + GPT-4.1-mini 88.8% at $0.26. This is a three-module system score (policy, localizer, validator) — [HF Holo1-7B](https://huggingface.co/Hcompany/Holo1-7B); paper [arXiv 2506.02865](https://arxiv.org/abs/2506.02865)
- Surfer 2, H's own (multi-model system): WebVoyager 97.1%, WebArena 69.6%, OSWorld 60.1%, AndroidWorld 87.1% — [arXiv 2510.19949](https://arxiv.org/abs/2510.19949)
- Surfer 2 with multiple attempts: WebVoyager 100% pass@10, WebArena 84.9% pass@10, OSWorld 77.0% at ten attempts; OSWorld human baseline 72.4%; reasoning by o3, GPT-4.1 and Claude Sonnet 4.5 with Holo1.5 as localiser — [alphaXiv overview of 2510.19949](https://www.alphaxiv.org/overview/2510.19949) (secondary, unverified against the PDF)
- Holo3, H's own: Holo3-122B-A10B 78.85% and Holo3-35B-A3B 77.8% on OSWorld-Verified; baselines evaluated by H except starred numbers; ScreenSpot-Pro and OSWorld-G figures exist only in an image table; an internal "H Corporate Benchmark" of 486 multi-step tasks is introduced without scores in text — [hcompany.ai/holo3](https://hcompany.ai/holo3); [HF Holo3-35B-A3B](https://huggingface.co/Hcompany/Holo3-35B-A3B)
- Independent-style listing: an OSWorld-Verified leaderboard mirror shows Holo3-35B-A3B at 80.4% ±2.2 (two runs, 296.41/359 and 280.55/359, 100 max steps, dated 20 Apr 2026, category "specialized model") — [yutori.com OSWorld-Verified mirror](https://yutori.com/leaderboards/osworld-verified.md) (seen via search summary only; not checked against os-world.github.io, so treat as unverified secondary)
- Holo3.1, H's own: AndroidWorld 35B-A3B 67% to 79.3%, and the 4B and 9B from 58% to 72%; FP8 and NVFP4 score about two points below BF16 on OSWorld; "more than 25%" better than Holo3 in the HoloTab harness — [HF blog: Holo3.1](https://huggingface.co/blog/hcompany/holo31)
- Holo3.1 OSWorld detail (H's own implementation, which H says differs slightly from OSWorld-Verified): 35B-A3B BF16 80.0%, FP8 77.8%, NVFP4 77.8% — [ChatForest builder guide](https://chatforest.com/builders-log/holo-3-1-local-computer-use-agent-12gb-gpu-builder-guide/) (secondary, attributing the figures to H)
- Holo4, H's own: Holo4-27B OSWorld 85.2% at $0.08 per task; OSWorld 2.0 Holo4-27B 61.7% at $1.22 and Holo4-35B-A3B 30.9% at $0.61; AutomationBench Holo4-27B 45.4% at $0.05 and Holo4-35B-A3B 34.5% at $0.02 — [HF Holo4-27B](https://huggingface.co/Hcompany/Holo4-27B); [HF Holo4-35B-A3B](https://huggingface.co/Hcompany/Holo4-35B-A3B)
- Holo4 versus closed models on OSWorld 2.0 (H's own blog): Holo4-27B 61.7% against 81.8% for Opus 5.5; a harness chart at max effort with partial rewards shows Opus 5 at 70.2% and GPT-5.6 Sol at 66.2% — [HF blog: Holo4](https://huggingface.co/blog/Hcompany/holo4)
- Holotron4-30B-A3B versus its Nemotron base (H's own): OSWorld 21.0 to 76.3; OSWorld 2.0 0.2 to 7.9; AutomationBench 19.4 to 35.6 — [HF Holotron4-30B-A3B](https://huggingface.co/Hcompany/Holotron4-30B-A3B)
- H publishes the agent trajectories behind its public-benchmark scores — [HF dataset Hcompany/trajectories](https://huggingface.co/datasets/Hcompany/trajectories)
- Secondary reports say H concedes its cross-model comparisons use different harnesses, effort settings and task subsets, and that Holo4-27B scores 49.3% on held-out tasks — [Superpower Daily](https://superpowerdaily.com/posts/h-company-releases-holo4-computer-use-models-with-different-self-hosting-rights); [Unite.AI](https://www.unite.ai/h-company-releases-holo4-open-weight-models-for-computer-use-agents/) (seen via search summary only; unverified)
- Independent hobbyist reproduction of Holo3.1-4B, quantised, on an RTX 4050 6 GB: Q5_K_M without zoom 59.5% ScreenSpot-Pro and 98.0% ScreenSpot-v2 at 2.4 s per click; with a second "zoom" crop pass 67.6 to 69.6% ScreenSpot-Pro; Holo3.1-9B IQ4_XS 61.5% ScreenSpot-Pro without zoom; plain Qwen3.5-9B IQ4_XS baseline 50.0% — [GitHub xmasdev/local-cua](https://github.com/xmasdev/local-cua)

### Inferences
- The size gap inside Holo4 on long tasks is large: on OSWorld 2.0 the Apache 35B-A3B scores half of the NC 27B (30.9 vs 61.7). The licence trade-off therefore has a real capability cost on hard, long-horizon work, though the gap on plain OSWorld is not published for the 35B-A3B in text.
- For browser-only work the most relevant single-model numbers found are the Holo2 WebVoyager figures (80.2% for 4B and 8B). No WebVoyager or Online-Mind2Web figures were found for Holo3, 3.1 or 4; H's emphasis shifted to desktop (OSWorld) and business-workflow benchmarks, which makes head-to-head comparison with web-only models such as Fara and MolmoWeb indirect.
- WebVoyager is known to be saturated and judged by an LLM; the Surfer-H and Surfer 2 figures should not be read as "Holo alone browses at 92 to 97%".
- A community reproduction landing close to H's ScreenSpot-Pro range for a 4B model, even at Q5 quantisation, is modest independent support for H's grounding claims.

### Gaps
- No Online-Mind2Web result for any Holo model found. No listing found for Holo on leaderboard.steel.dev. No ScreenSpot-Pro leaderboard entry confirmed (search returned nothing).
- No Holo source was found that compares directly against Microsoft Fara or Ai2 MolmoWeb.
- ScreenSpot-Pro / OSWorld-G for Holo3, Holo3.1 and Holo4, and per-size OSWorld for Holo3.1 4B and 9B, exist only as image tables that could not be read.
- OSWorld 2.0 and AutomationBench are newer benchmarks; their maintainers and whether H's runs are verified were not checked.

## 5. Running locally: quantised builds, memory, Apple Silicon, speed, cost

### Takeaway
Local running is a first-class path since Holo3.1: H publishes official Q4_K_M GGUFs (with a vision projector) for the 35B-A3B models and Holo4-27B, and documents llama.cpp on Apple Silicon and vLLM on NVIDIA. The catch is speed on a Mac: H's own figure for Holo3.1-35B-A3B Q4 on a MacBook M4 Pro is 3.6 requests per minute, roughly 17 seconds per step. No official MLX builds were found; Ollama coverage is via `hf.co/...` pulls or community uploads.

### Cited Findings
- H's recommended hardware table (weights only; KV cache and image encoder are extra): Mac M3 or newer with 36 GB+ for Holo3.1-35B-A3B Q4_K_M GGUF via llama.cpp (21.3 GB); DGX Spark for NVFP4 via vLLM (23.7 GB); single 24 GB GPU for Holo3.1-9B BF16 (18.8 GB); single 16 GB GPU for Holo3.1-4B BF16 (10.4 GB); on-device for Holo3.1-0.8B BF16 (2.2 GB) — [H hub local inference](https://hub.hcompany.ai/agents-api/local-inference.md)
- Holo4 weight sizes: 27B BF16 54.7 GB, FP8 35.9 GB, NVFP4 22.9 GB; 35B-A3B BF16 70.2 GB, FP8 37.6 GB, NVFP4 22.5 GB, Q4 GGUF 21.3 GB — [H hub local inference](https://hub.hcompany.ai/agents-api/local-inference.md)
- Official Holo4-27B GGUF repo: `q4_k_m.gguf` 16.9 GB plus `mmproj.f16.gguf` 928 MB (17.8 GB total), tag cc-by-nc-4.0; the auto-generated run snippets reference an `:F16` tag that does not match the single Q4 file — [HF Holo4-27B-GGUF files](https://huggingface.co/Hcompany/Holo4-27B-GGUF/tree/main)
- Official Holo4-35B-A3B GGUF repo: `q4_k_m.gguf` 21.3 GB plus `mmproj.f16.gguf` 899 MB (22.2 GB total), tag apache-2.0 — [HF Holo4-35B-A3B-GGUF files](https://huggingface.co/Hcompany/Holo4-35B-A3B-GGUF/tree/main)
- Mac recipe from H: `brew install llama.cpp` then `llama-server -hf Hcompany/Holo-3.1-35B-A3B-GGUF` (or `Hcompany/Holo4-35B-A3B-GGUF`), with tuned flags including `--ctx-size 65536`, `--image-min-tokens 1024`, `--cache-ram 32768`, q8_0 KV cache; the server ignores the API key and "prompts and screenshots never leave your network" — [H hub local inference](https://hub.hcompany.ai/agents-api/local-inference.md)
- H's measured agent throughput for Holo3.1-35B-A3B in the Holo CLI: MacBook M4 Pro, Q4, llama.cpp 3.6 requests/min; DGX Spark FP8 vLLM 8.9; DGX Spark Q4 llama.cpp 9.5; DGX Spark NVFP4 vLLM 13.5 — [H hub local inference](https://hub.hcompany.ai/agents-api/local-inference.md)
- On DGX Spark, average step time fell from 6.8 s (FP8 baseline) to 3.3 s with NVFP4 plus harness optimisations; NVFP4 gives 1.41x FP8 and 1.74x BF16 token throughput — [HF blog: Holo3.1](https://huggingface.co/blog/hcompany/holo31)
- A "fast" harness mode lifts the M4 Pro figure to 5.5 requests/min (about 10.9 s per step), and H's chart notes that llama.cpp lacks prefix or image caching for this architecture — [ChatForest builder guide](https://chatforest.com/builders-log/holo-3-1-local-computer-use-agent-12gb-gpu-builder-guide/) (secondary, attributing to H; the same guide flags a third-party "140 ms per step on an RTX 4090" claim as uncorroborated)
- Small-model evidence: Holo3.1-4B Q5_K_M runs fully on a 6 GB RTX 4050 laptop GPU with an 80k-token context at 2.33 s per quick step and 3.48 s per thinking step (1280 image tokens), about 46 tok/s; the 9B does not fit in 6 GB and runs about half as fast; Q4 versus Q5 is "barely faster and less accurate" — [GitHub xmasdev/local-cua](https://github.com/xmasdev/local-cua)
- Community GGUF conversions for the smaller Holo3.1 sizes come from mradermacher and unsloth (credited by a community repo); Holo cards link "quantized models" counts (for example 6 for Holo-3.1-9B, 8 for Holo-3.1-4B, 14 for Holo4-27B, 17 for Holo4-35B-A3B) usable in llama.cpp, Ollama and LM Studio — [GitHub xmasdev/local-cua](https://github.com/xmasdev/local-cua); [HF Holo-3.1-9B](https://huggingface.co/Hcompany/Holo-3.1-9B); [HF Holo4-27B](https://huggingface.co/Hcompany/Holo4-27B)
- Ollama: the official GGUF repos show `ollama run hf.co/Hcompany/Holo4-27B-GGUF:...` snippets; a secondary guide says the Ollama library had only a community upload covering 0.8B and 4B — [HF Holo4-27B-GGUF files](https://huggingface.co/Hcompany/Holo4-27B-GGUF/tree/main); [ChatForest builder guide](https://chatforest.com/builders-log/holo-3-1-local-computer-use-agent-12gb-gpu-builder-guide/) (the latter unverified)
- Hosted cost points: Holo3 about $3 per million output tokens for the 122B and about $1.8 for the 35B (figure alt text), with a free tier for the 35B; Holo4 cost per task $0.02 to $1.22 depending on benchmark and size — [hcompany.ai/holo3](https://hcompany.ai/holo3); [HF Holo4-27B](https://huggingface.co/Hcompany/Holo4-27B)

### Inferences
- On a 32 to 64 GB Apple Silicon Mac, Holo4-27B Q4 (16.9 GB + 0.9 GB projector + KV cache) is the smallest-footprint route to the strongest Holo; the 35B-A3B Q4 needs about 4.4 GB more for weights. H's Mac recommendation is 36 GB+ for the 35B-A3B.
- Expect roughly 10 to 17 seconds per step on M4 Pro class hardware for the 35B-A3B per H's own numbers; a 20-step browser task would take several minutes. The 27B is dense, so every token touches all 27B parameters, and it will likely be slower per token than the 35B-A3B (3B active). No Mac number for the 27B was found.
- Holo3.1-4B or 9B via GGUF are the realistic "fast local" options (seconds per step on a small GPU), at lower task success.
- Electricity aside, local cost per task is zero; the hosted figures show H positions cost, not peak accuracy, as its advantage over closed frontier models.

### Gaps
- No official MLX build was found on any card read, and MLX was not searched for among community uploads.
- No Apple Silicon speed figures for Holo4 (either size) or for Holo3.1 4B / 9B.
- LM Studio support is only a generic "open in LM Studio" link; no confirmation that the vision projector and tool-call template work there.
- No end-to-end wall-clock or cost-per-task figure for a web task run fully locally.

## 6. Safety behaviour: approvals, refusals, prompt injection, usage restrictions

### Takeaway
Safety in the Holo ecosystem lives in the harness and platform, not the model. H's Agents API has tool approvals, pause and steer controls, credential vaults and a local kill switch, but no model card read has a safety or limitations section, and no primary source describes trained-in stop-for-approval at critical points, refusal behaviour or prompt-injection handling.

### Cited Findings
- None of the model cards read (Holo1-7B, Holo1.5-7B, Holo2-4B, Holo2-30B-A3B, Holo3-35B-A3B, Holo-3.1-4B, Holo-3.1-9B, Holo4-27B, Holo4-35B-A3B) has a limitations or safety section — [HF Holo4-27B](https://huggingface.co/Hcompany/Holo4-27B); [HF Holo3-35B-A3B](https://huggingface.co/Hcompany/Holo3-35B-A3B); [HF Holo2-30B-A3B](https://huggingface.co/Hcompany/Holo2-30B-A3B)
- The Holo3, Holo3.1 and Holo4 launch posts make no safety statements — [hcompany.ai/holo3](https://hcompany.ai/holo3); [HF blog: Holo3.1](https://huggingface.co/blog/hcompany/holo31); [HF blog: Holo4](https://huggingface.co/blog/Hcompany/holo4)
- Agents API tool approvals: a tool call can be held in `pending_approvals` until a human approves or denies it via `POST /sessions/{id}/tool_approvals`; a denial can carry a message to the model. The page does not say which actions are held by default or whether GUI actions such as clicking Submit or Buy are gated — [H hub: tool approvals](https://hub.hcompany.ai/agents-api/sessions/tool-approvals.md)
- Session controls: `send_message`, `pause`, `resume`, `force_answer`, `cancel`; Esc pauses an interactive session, double Esc stops the desktop agent (kill switch on macOS, Windows and X11 Linux); `holo local stop` halts local turns — [GitHub hcompai/hai-agents-python](https://github.com/hcompai/hai-agents-python)
- Credentials: vaults (1Password or H-hosted) let the agent sign in with secrets that "never enter its context"; an OTP tool runs in the user's process and hands the agent only the code. Vaults are a cloud-browser feature; in "your browser" mode your own Chrome's logins replace them — [GitHub hcompai/hai-agents-python](https://github.com/hcompai/hai-agents-python); [H hub: Your browser](https://hub.hcompany.ai/agents-api/your-browser.md)
- H's own warning for local browser mode: the agent acts on your real browser with your logins and network, can run page scripts and read that Chrome's cookies and storage, and H recommends a dedicated machine over your primary one — [H hub: Your browser](https://hub.hcompany.ai/agents-api/your-browser.md)
- HoloTab shows its reasoning live (current tab, next step) and one example has it draft email replies "for approval" — [hcompany.ai/holotab](https://hcompany.ai/holotab)
- A community harness had to add its own gate: elements named Send, Delete, Remove, Pay, Buy, Submit or Publish (and Ctrl+Enter) need user approval, and are refused if nobody answers; the author advises a "prepare it, don't send it" habit with a 4B model — [GitHub xmasdev/local-cua](https://github.com/xmasdev/local-cua)
- Usage restrictions come from licences only: CC BY-NC 4.0 on Holo4-27B and Holo2-30B-A3B, research-only on Holo1.5-72B, NVIDIA Open Model Agreement on Holotron4 — [HF Holo4-27B](https://huggingface.co/Hcompany/Holo4-27B); [HF Holo1.5-7B](https://huggingface.co/Hcompany/Holo1.5-7B); [HF Holotron4-30B-A3B](https://huggingface.co/Hcompany/Holotron4-30B-A3B)

### Inferences
- Anyone running Holo weights locally with their own loop gets no built-in safety layer; approval gates on irreversible actions, domain allowlists and prompt-injection defences must be built in the harness. This is a clear contrast point if the Fara or MolmoWeb researchers find model-level "critical point" stopping or refusal training.
- H's recommendation to use a dedicated machine, plus the dedicated Chrome profile, is effectively the vendor's prompt-injection mitigation: limit what the agent's browser can reach.

### Gaps
- No primary source found on prompt-injection robustness, refusal behaviour or red-teaming of any Holo model. Absence in the pages read is not proof that none exists; the HoloTab FAQ safety answers and the Agents API "Watch and steer" page were not read.
- Default approval policy for H's pre-built agents (`h/web-surfer-flash`, `h/web-surfer-pro`) is unknown.

## 7. Known weaknesses and criticisms

### Takeaway
The weaknesses that can be sourced are: self-reported and partly unreadable benchmarks with shifting harnesses; a steep fall-off on long-horizon tasks, especially for the Apache 35B-A3B; slow steps on Apple Silicon; persistent misses on tiny targets; an ecosystem that keeps deprecating its open harnesses and steering users to H's hosted platform; and very thin independent community evaluation. No Hacker News or r/LocalLLaMA threads on Holo3, 3.1 or 4 were found by search.

### Cited Findings
- H's own Holo4 post concedes Holo4 trails the strongest closed models on long workflows (61.7% vs 81.8% for Opus 5.5 on OSWorld 2.0) and that the 35B-A3B reaches only 30.9% — [HF blog: Holo4](https://huggingface.co/blog/Hcompany/holo4)
- Reported held-out score for Holo4-27B is 49.3%, well under the 85.2% public OSWorld headline, and H's cross-model comparisons mix harnesses, effort settings and task subsets — [Superpower Daily](https://superpowerdaily.com/posts/h-company-releases-holo4-computer-use-models-with-different-self-hosting-rights) (search summary only; unverified)
- Holo3.1's OSWorld numbers come from H's own implementation, which "differs slightly" from OSWorld-Verified, and quantised builds lose about two points — [ChatForest builder guide](https://chatforest.com/builders-log/holo-3-1-local-computer-use-agent-12gb-gpu-builder-guide/) (secondary); [HF blog: Holo3.1](https://huggingface.co/blog/hcompany/holo31)
- Key benchmark tables on the Holo3, Holo3.1 and Holo4 cards are published as images, not text; the Holo2 card shipped with a note that bold SOTA marks would be added "once final evaluations are available" — [HF Holo3-35B-A3B](https://huggingface.co/Hcompany/Holo3-35B-A3B); [HF Holo2-30B-A3B](https://huggingface.co/Hcompany/Holo2-30B-A3B)
- Surfer 2 failure analysis: WebVoyager failures mainly from anti-bot measures such as CAPTCHAs; localisation errors persist; context limits constrain very long tasks; e-commerce lags (58% vs 77% on Reddit in WebArena); AndroidWorld hard tasks 52.6% vs 98.4% easy — [alphaXiv overview of 2510.19949](https://www.alphaxiv.org/overview/2510.19949) (secondary summary)
- The Surfer 2 abstract itself says results call for "a next-generation vision language model to achieve Pareto-optimal cost-efficiency", i.e. the 2025 headline system was expensive because it leaned on frontier models — [arXiv 2510.19949](https://arxiv.org/abs/2510.19949)
- Hands-on report with Holo3.1-4B: simple and medium tasks work; long multi-step tasks "wander" and take roundabout paths; tiny icons in dense apps are missed "about one in three" even with a zoom pass; the zoom pass adds about 10 points on hard screens for about 1.4 s per click; needed loop detection that stops after three warnings — [GitHub xmasdev/local-cua](https://github.com/xmasdev/local-cua)
- Speculative decoding with Holo3.1-0.8B as a draft model was slower (34 to 38 tok/s vs 46) because llama.cpp cannot pass image embeddings to the draft model — [GitHub xmasdev/local-cua](https://github.com/xmasdev/local-cua)
- Mac speed is the practical ceiling: 3.6 requests per minute for Holo3.1-35B-A3B Q4 on an M4 Pro — [H hub local inference](https://hub.hcompany.ai/agents-api/local-inference.md)
- Ecosystem churn: surfer-h-cli is archived and unmaintained; the Holo1 / Holo1.5 demo Spaces are in build-error or paused state; the hub's model comparison and changelog URLs now 404 — [GitHub hcompai/surfer-h-cli](https://github.com/hcompai/surfer-h-cli); [HF Hcompany org](https://huggingface.co/Hcompany)
- The current harness is hosted-first: `hai-agents` needs an `HAI_API_KEY`, agents "run on hosted infrastructure by default", and the repo is small (46 stars, 4 open issues) — [GitHub hcompai/hai-agents-python](https://github.com/hcompai/hai-agents-python)
- Card hygiene issues: the Holo2-30B-A3B card states both CC BY-NC and Apache 2.0; the Holo-3.1-4B repo reports 5B parameters; the Holo3.1 model tree lists Qwen3.5-0.8B as the parent on the 4B and 9B cards; the Holo4-27B GGUF snippets reference a non-existent F16 tag — [HF Holo2-30B-A3B](https://huggingface.co/Hcompany/Holo2-30B-A3B); [HF Holo-3.1-4B](https://huggingface.co/Hcompany/Holo-3.1-4B); [HF Holo4-27B-GGUF files](https://huggingface.co/Hcompany/Holo4-27B-GGUF/tree/main)
- The OSWorld-Verified field has moved past Holo3: a 29 Oct 2026 snapshot lists Qwen3.8 Max at 86.1% and Anthropic models at 85% — [BenchLM OSWorld-Verified](https://benchlm.ai/md/benchmarks/osworld-verified.md) (search summary only; unverified)

### Inferences
- Holo's strengths for this use case: a real choice of sizes with official GGUFs, Apache options from 0.8B to 35B-A3B, documented Apple Silicon path, screenshot-only generality across web, desktop and mobile, and published trajectories. Its weaknesses: benchmark emphasis has drifted away from web-only tasks, safety is left to the harness, the strongest sub-32B model is non-commercial, and the vendor's incentive is to move users to its hosted Agents API.
- Because Holo models are fine-tunes of Qwen VLMs, much of the generation-to-generation gain tracks the Qwen base (Qwen2.5-VL, Qwen3-VL, Qwen3.5, Qwen3.6 / 3.8); H's own tables show the base models close behind on some navigation rows (for example Qwen3-VL-30B-A3B-Thinking 45.0% vs Holo2-30B-A3B 46.3% on WebArena).

### Gaps
- No Reddit r/LocalLLaMA or Hacker News discussion of Holo3, Holo3.1 or Holo4 was surfaced by two targeted searches; Hugging Face discussion tabs and GitHub issue contents were not read. Community sentiment is therefore under-sampled, resting on one hobbyist repo.
- No independent replication of any Holo4 number was found.
- No evidence either way on how Holo models behave on logged-in, real-world sites with CAPTCHAs or bot detection when run locally.
