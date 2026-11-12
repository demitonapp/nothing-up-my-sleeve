# Ai2 MolmoWeb (4B / 8B open-weight visual web agent) — state as of 12 November 2026

Method note: facts below were read from the primary pages on 12 Nov 2026 (Hugging Face cards, GitHub repo and its API, arXiv HTML v1, Ai2 blog). Web pages were read through a summarising fetch tool, so short quotes are as that tool returned them; five source files from the GitHub repo were downloaded and grepped directly. Anything found only in press or third-party pages is marked "unverified (secondary)".

## 1. Sizes, backbones, licences, follow-up releases

### Takeaway
Two sizes, MolmoWeb-4B (about 5B parameters on disk) and MolmoWeb-8B (about 9B), both Molmo2-architecture models with a Qwen3 language model and a SigLIP 2 vision encoder; weights and code are Apache 2.0, the human-trajectory dataset is ODC-BY 1.0. There has been no second model version: the only changes since the 24 March 2026 launch are a checkpoint fix (29 March), the code/eval/training release (10 April), and harness additions (Odysseys benchmark in June, Browser Use Cloud environment in September).

### Cited Findings
- Announced 24 March 2026 by Ai2; "code release update" on 10 April 2026. Two sizes, 4B and 8B, built on the Molmo 2 family — [Ai2 blog](https://allenai.org/blog/molmoweb)
- Paper: "MolmoWeb: Open Visual Web Agent and Open Data for the Open Web", arXiv 2604.08516, submitted 9 April 2026, only v1 exists; 16 authors led by Tanmay Gupta, with Ali Farhadi and Ranjay Krishna last — [arXiv abs](https://arxiv.org/abs/2604.08516)
- Architecture per paper (Sec. 3.1, 3.3): Molmo2 with a Qwen3 LLM and SigLIP2 vision encoder — [arXiv HTML](https://arxiv.org/html/2604.08516v1)
- MolmoWeb-8B card: licence Apache 2.0, "intended for research and educational use in accordance with Ai2's Responsible Use Guidelines"; finetuned from Qwen3-8B (base listed as Qwen3-8B-Base) with SigLIP 2; safetensors report 9B params, F32 — [HF MolmoWeb-8B](https://huggingface.co/allenai/MolmoWeb-8B)
- MolmoWeb-4B card: `license: apache-2.0`; `base_model` lists Qwen/Qwen3-8B and google/siglip-so400m-patch14-384; text says "MolmoWeb-4B is based on Molmo2 architecture, which uses Qwen3-8B and SigLIP 2 as vision backbone"; safetensors report 5B params, F32 — [HF MolmoWeb-4B README raw](https://huggingface.co/allenai/MolmoWeb-4B/raw/main/README.md), [HF MolmoWeb-4B](https://huggingface.co/allenai/MolmoWeb-4B)
- The underlying Molmo2-4B card lists Qwen/Qwen3-4B-Instruct-2507 as its LLM base, with SigLIP 2, 5B params — [HF Molmo2-4B](https://huggingface.co/allenai/Molmo2-4B). This conflicts with the MolmoWeb-4B card's "Qwen3-8B" wording (see Inferences).
- Checkpoints listed in the repo: MolmoWeb-8B and MolmoWeb-4B (HF/transformers-compatible), MolmoWeb-8B-Native and MolmoWeb-4B-Native (molmo-native format), MolmoWeb-Pretrained-8B and -4B (the starting checkpoints for SFT training) — [GitHub allenai/molmoweb](https://github.com/allenai/molmoweb)
- Code licence: Apache 2.0 (GitHub API `license.spdx_id: Apache-2.0`) — [GitHub API](https://api.github.com/repos/allenai/molmoweb)
- Data licence: MolmoWeb-HumanTrajs is "licensed under ODC-BY 1.0", for research and educational use under Ai2's Responsible Use Guidelines; instruction text generated with Gemini Flash and GPT models is additionally "subject to" Google's and OpenAI's terms — [HF dataset MolmoWeb-HumanTrajs](https://huggingface.co/datasets/allenai/MolmoWeb-HumanTrajs)
- Six datasets are named in the model card front matter: MolmoWeb-SyntheticTraj(s), HumanTrajs, HumanSkills, SyntheticSkills, SyntheticQA, SyntheticGround — [HF MolmoWeb-4B README raw](https://huggingface.co/allenai/MolmoWeb-4B/raw/main/README.md)
- Checkpoint fix: the HF/transformers checkpoints were updated 29 March 2026 (~6 PM PST) to match native-checkpoint outputs; earlier downloads should be re-fetched — [HF MolmoWeb-8B](https://huggingface.co/allenai/MolmoWeb-8B)
- Repo activity (GitHub API, read 12 Nov 2026): last push 2026-09-05; 596 stars, 81 forks; no releases or tags shown. Recent commits: Odysseys benchmark support (22 May, merged 9 June 2026), dependabot bump (June), Browser Use Cloud environment (26 Aug to 5 Sep 2026) — [GitHub API commits](https://api.github.com/repos/allenai/molmoweb/commits?per_page=8)
- A Hugging Face search for "molmoweb" returns 17 model repos; the Ai2 ones are the six above, all last updated 10 to 13 April 2026. No "MolmoWeb 2", "MolmoWeb-1.5" or larger size appears — [HF model search](https://huggingface.co/models?search=molmoweb)
- A web search for a newer version or update found only March–April 2026 launch coverage — [VentureBeat](https://venturebeat.com/data/ai2-releases-molmoweb-an-open-weight-visual-web-agent-with-30k-human-task), [Ai2 April 2026 newsletter](https://allenai.org/newsletters/2026-04-newsletter)

### Inferences
- The MolmoWeb-4B card's "Qwen3-8B" is almost certainly a copy-paste error from the 8B card: the file is 5B parameters and Molmo2-4B is documented as Qwen3-4B-Instruct. Treat "4B = Qwen3-4B + SigLIP 2 so400m (about 0.4B) + connector" and "8B = Qwen3-8B + SigLIP 2" as the working reading, but note the card itself does not say so.
- The "4B"/"8B" names refer to the LLM; with the vision tower the real sizes are about 5B and 9B. Both are far below a 32B ceiling.
- "Apache 2.0" plus "intended for research and educational use" is a mixed signal: the licence text permits commercial use, the card's intended-use sentence and the Responsible Use Guidelines are softer guidance. For a non-commercial local project this is not a constraint.
- No model refresh in about 7.5 months, and the last code push was September 2026, so the project looks maintained at a low rate rather than actively versioned.

### Gaps
- I did not open the licence field of the five sibling datasets individually; only HumanTrajs is confirmed as ODC-BY 1.0.
- The paper describes a dedicated grounding model "MolmoWeb-Ground-8B"; I did not see it in the Hugging Face search listing, so whether it was released is unconfirmed.
- I did not read Ai2's Responsible Use Guidelines page itself.
- The Molmo2-8B card was not read, so "Qwen3-8B" for the 8B rests on the MolmoWeb-8B card alone.

## 2. Inputs, outputs, action space, harness, attaching to an existing Chrome

### Takeaway
MolmoWeb is screenshot-only: each step gets the task, one 1280x720 screenshot, the URL/title and a text log of earlier thoughts and actions, and emits a short thought followed by one action with coordinates normalised to 0–100. The reference harness is a Python client that drives Playwright Chromium (local, Browserbase or Browser Use Cloud) against a small `/predict` server; it launches a fresh non-persistent browser context and has no built-in option to attach to a user's logged-in Chrome.

### Cited Findings
- The agent predicts the next browser action from a task instruction and a webpage screenshot "without HTML, accessibility trees, or specialized APIs" (paraphrase of abstract) — [arXiv abs](https://arxiv.org/abs/2604.08516)
- Per-step inputs: task instruction, screenshot of the current view, recent action history; outputs: a short natural-language thought, then the next action — [Ai2 blog](https://allenai.org/blog/molmoweb)
- Prompt template sections: "# GOAL", "# PREVIOUS STEPS" (step index, THOUGHT, ACTION), "# CURRENTLY ACTIVE PAGE" (page index, title, URL), "# NEXT STEP"; system string `molmo_web_think`; example uses a 1280x720 screenshot and `max_new_tokens=200` — [HF MolmoWeb-8B](https://huggingface.co/allenai/MolmoWeb-8B)
- Action space (paper Table 3): goto(url), mouse_click(x, y), mouse_drag_and_drop, scroll, scroll_at, hover_at, keyboard_type, keyboard_press, go_back, new_tab, tab_focus, noop(wait_ms), send_msg_to_user. Output is a JSON object with "thought" and "action"; mouse coordinates are normalised to [0, 100] with two decimals and converted to viewport pixels at execution — [arXiv HTML](https://arxiv.org/html/2604.08516v1)
- The repo's `agent/actions.py` additionally defines `report_infeasible` (with a reason string), mouse move, select-all and a browser-navigation action — [agent/actions.py](https://github.com/allenai/molmoweb/blob/main/agent/actions.py)
- Client defaults in code: viewport 1280x720; `max_past_steps=10`, `max_past_images=0` (history is text only, one image per step); `run(query, max_steps=15)` — [inference/client.py](https://github.com/allenai/molmoweb/blob/main/inference/client.py)
- Server: `scripts/start_server.sh` with `PREDICTOR_TYPE` `native` (default) or `hf`, `NUM_PREDICTORS` GPU workers, port 8001, endpoint `POST /predict` taking `prompt` and `image_base64`. Backends listed: fastapi, modal, native, hf — [GitHub README](https://raw.githubusercontent.com/allenai/molmoweb/main/README.md)
- Browser environments: `simple` (local Chromium via Playwright), `browserbase` (API key, default cloud provider), `browser_use` (Browser Use Cloud, added Sept 2026). Install step is `playwright install --with-deps chromium`; Python >=3.10,<3.13 — [GitHub README](https://raw.githubusercontent.com/allenai/molmoweb/main/README.md)
- Local environment code: `SimpleEnv` calls `playwright.chromium.launch(headless=..., args=["--disable-blink-features=AutomationControlled"], channel=...)` then `browser.new_context(viewport=...)`. It accepts `headless` and an optional `channel`, but there is no `launch_persistent_context`, `user_data_dir`, `storage_state` or local `connect_over_cdp`; `connect_over_cdp` is used only for Browserbase and Browser Use sessions — [utils/envs/browser_env.py](https://github.com/allenai/molmoweb/blob/main/utils/envs/browser_env.py)
- The client can also extract an accessibility tree (used by the repo's Gemini/GPT AxTree baseline agents and for data generation), but the MolmoWeb model does not consume it — [GitHub allenai/molmoweb](https://github.com/allenai/molmoweb)
- HF predictor defaults in code: `temperature=0.7`, `top_p=0.8`, `max_new_tokens=1024`, float32, sdpa attention — [agent/model_backends.py](https://github.com/allenai/molmoweb/blob/main/agent/model_backends.py)
- VentureBeat (secondary, consistent with primary): it "works with any browser that can provide screenshots"; the hosted demo uses Browserbase — [VentureBeat](https://venturebeat.com/data/ai2-releases-molmoweb-an-open-weight-visual-web-agent-with-30k-human-task)

### Inferences
- Attaching to an existing logged-in Chrome is not offered but is a small change: the harness already uses Playwright `connect_over_cdp` for cloud browsers, so pointing it at a local Chrome started with `--remote-debugging-port` (or swapping in a persistent context) is a few lines in a subclass of the environment. Equally, because the model server is just prompt + base64 image in, text out, a custom harness (including a Chrome extension) is feasible. This is my reading of the code, not a documented feature.
- The viewport is fixed at 1280x720 in the client; a user's real Chrome window would need to be sized or screenshots rescaled to match what the model was trained on. Coordinates being normalised 0–100 makes rescaling straightforward.
- Sampling at temperature 0.7 by default means runs are not deterministic, which is consistent with the paper's emphasis on multiple rollouts.
- With `max_past_images=0` the model never sees earlier screenshots, only its own text thoughts; any state it must remember has to be written into a thought.

### Gaps
- The paper's exact image resolution/crop scheme and token count per screenshot were not extracted.
- No documentation of a headed, persistent-profile mode was found; whether Ai2 intends one is unknown.

## 3. Benchmark results, who ran them, judges, pass@1 vs pass@4

### Takeaway
The 78.2% WebVoyager / 35.3% Online-Mind2Web (single rollout) and 94.7% / 60.5% (pass@4) figures for the 8B are confirmed in the paper, blog and model card, and all are Ai2's own runs scored by LLM judges; the pass@4 numbers are a best-of-several statistic and are not comparable to other agents' single-run scores. I found no independent re-evaluation, and MolmoWeb is not listed on the Steel.dev WebVoyager leaderboard.

### Cited Findings
- Paper Table 4 (success %, max 100 steps), MolmoWeb-8B: WebVoyager 78.2, Online-Mind2Web 35.3, DeepShop 42.3, WebTailBench 49.5. MolmoWeb-4B: 75.2, 31.3, 35.6, 43.8 — [arXiv HTML](https://arxiv.org/html/2604.08516v1)
- Same table, baselines: Fara-7B 73.5 / 34.1 / 26.2 / 38.4; UI-TARS-1.5-7B 66.4 / 31.3 / 11.6 / 19.5; GLM-4.1V-9B-Thinking 66.8 / 33.9 / 32.0 / 22.4; Holo1-7B 55.4 on WebVoyager only, at 30 steps; SoM GPT-4o 65.1 / 34.6 / 16.0 / 30.8; SoM o3 79.3 / 55.4 / 49.7 / 52.7; SoM GPT-5 90.6 / 57.7 / 49.1 / 60.4; OpenAI CUA 70.9 / 58.3 / 24.7 / 25.7; Gemini computer-use 88.6 / 57.3 / 62.0 / 63.0 — [arXiv HTML](https://arxiv.org/html/2604.08516v1)
- Provenance of baselines: the starred rows (Fara-7B, UI-TARS-1.5-7B, GLM-4.1V, SoM GPT-4o/o3/GPT-5, OpenAI CUA) are copied from the Fara paper, not re-run by Ai2 — [arXiv HTML](https://arxiv.org/html/2604.08516v1)
- Judges: GPT-4o with the official prompt for WebVoyager and DeepShop; o4-mini (WebJudge) for Online-Mind2Web; WebTailBench scored with the WebVoyager judge because, per Ai2, the source paper does not specify one (daggered values) — [arXiv HTML](https://arxiv.org/html/2604.08516v1)
- Protocol: 3–5 runs per model averaged, up to 100 steps, up to 10 retries per trajectory, run on Browserbase hosted browsers — [arXiv HTML](https://arxiv.org/html/2604.08516v1)
- Pass@4: 94.7% WebVoyager and 60.5% Online-Mind2Web for the 8B, versus 78.2% and 35.3% single-rollout; estimated with an unbiased combinatorial pass@k formula from m = 5 rollouts per task, with "the respective judge" for each benchmark choosing the successful/best rollout — [arXiv HTML](https://arxiv.org/html/2604.08516v1); abstract wording is pass@4 "with best-of-N selection" — [arXiv abs](https://arxiv.org/abs/2604.08516)
- Equal-budget variant: three parallel 30-step runs (90 steps total) reach 86.2% on WebVoyager versus 78.2% for one 100-step run — [arXiv HTML](https://arxiv.org/html/2604.08516v1)
- Model card repeats 78.2 → 94.7 and 35.3 → 60.5 for the 8B and gives no DeepShop, WebTailBench or ScreenSpot numbers, and does not name the judge — [HF MolmoWeb-8B](https://huggingface.co/allenai/MolmoWeb-8B)
- Blog: all four benchmarks "use a VLM judge"; the 4B at a 30-step limit still beats Fara-7B given 100 steps (claim as stated by Ai2) — [Ai2 blog](https://allenai.org/blog/molmoweb)
- Grounding (paper Table 8), ScreenSpot / ScreenSpot-v2: MolmoWeb-Ground-8B 88.7 / 91.8; MolmoWeb-4B (general agent) 87.2 / 89.5; Holo1-7B 87.4 / 89.9; Fara-7B 86.7 / 89.3; Gemini-3-Pro – / 93.7. ScreenSpot-Pro is not reported — [arXiv HTML](https://arxiv.org/html/2604.08516v1)
- The Decoder notes the proprietary comparison points on ScreenSpot (Claude 3.7, OpenAI CUA) are older models, and that MolmoWeb trails its own Gemini-based AxTree "teacher" agent by five points — [The Decoder](https://the-decoder.com/ai2s-fully-open-web-agent-molmoweb-navigates-the-web-using-only-screenshots/) (unverified (secondary) for the five-point figure; I did not locate the table in the paper)
- Reproducibility caveats from maintainers: running the same weights under vLLM rather than the native/HF backend can move end-of-episode WebVoyager and Online-Mind2Web results "by up to ±10%" because of attention-backend logit differences; "extra caution" advised — [GitHub issue #17](https://github.com/allenai/molmoweb/issues/17)
- Open issue (24 Oct 2026): region-dependent websites in the local `simple` environment cause run-to-run instability — [GitHub issues list](https://github.com/allenai/molmoweb/issues?q=is%3Aissue)
- Independent leaderboards: MolmoWeb and Fara-7B are not listed on Steel.dev's WebVoyager leaderboard (last updated 11 Oct 2026), whose top rows are 97–99% from frontier-model harnesses; Holo appears there only inside H Company's mixed stacks (Surfer 2 97.1%, Surfer-H + Holo1 92.2%) — [Steel WebVoyager leaderboard](https://leaderboard.steel.dev/leaderboards/webvoyager/), [Steel leaderboard home](https://leaderboard.steel.dev/)
- An issue titled "Verify evals on Papers with Code" (opened by a Hugging Face staffer, closed 30 July 2026) exists; I did not read its outcome — [GitHub issues list](https://github.com/allenai/molmoweb/issues?q=is%3Aissue)

### Inferences
- The fair headline for a comparison table is single-rollout: 8B 78.2 / 35.3 / 42.3 / 49.5; 4B 75.2 / 31.3 / 35.6 / 43.8. Pass@4 needs four or five full rollouts plus a judge to pick the winner; in the paper that judge is the benchmark's own GPT-4o / o4-mini success judge, so pass@4 is closer to "at least one of four attempts succeeds" than to a deployable local pipeline. A local user without a strong judge model cannot realise 94.7%.
- The margin over Fara-7B on Online-Mind2Web is small (35.3 vs 34.1) and the Fara numbers come from a different lab's harness; given the ±10% backend sensitivity Ai2 itself reports, the two are effectively tied there. The DeepShop and WebTailBench gaps (42.3 vs 26.2; 49.5 vs 38.4) are larger, but the WebTailBench judge was Ai2's choice.
- The Holo1-7B comparison is weak evidence: one benchmark, 30 steps versus 100, and Holo1 rather than later Holo versions.
- On Online-Mind2Web the 8B is about 20 points behind frontier computer-use systems (35 vs 55–58), so hard, long-tail sites remain a real gap for any model this size.
- Synthetic training tasks were generated using WebVoyager and Online-Mind2Web tasks as in-context examples and templates aimed at WebVoyager sites (paper appendix B.2.4, C.1.1–C.1.2 — [arXiv HTML](https://arxiv.org/html/2604.08516v1)), so WebVoyager performance in particular may overstate out-of-distribution ability.

### Gaps
- No independent third-party re-evaluation of MolmoWeb was found (searched Steel.dev, general web, community). I did not open the official Online-Mind2Web leaderboard or the Steel Online-Mind2Web sub-page, so absence there is unconfirmed.
- I read the pass@k description through a summariser; the exact selector mechanics (oracle any-of-k versus a judge ranking rollouts without ground truth) should be checked in the paper before quoting.
- 4B pass@4 numbers, and pass@4 for DeepShop/WebTailBench, were not found.

## 4. Running locally: quantised builds, memory, Apple Silicon, speed

### Takeaway
Ai2 ships only full-precision float32 safetensors and a CUDA-oriented PyTorch server; there is no official GGUF, MLX, Ollama or LM Studio build, and no published VRAM, latency or tokens-per-second figures. Two small community 8-bit conversions exist (one MLX, 12.9 GB for the 8B) with empty or copied READMEs and no accuracy checks, and an Apple Silicon user reported MPS and Playwright breakage in April 2026.

### Cited Findings
- Official weights are F32 safetensors, 5B (4B model) and 9B (8B model) parameters; the card lists no quantisations in the model tree; serving options shown by the Hub are vLLM, SGLang, Docker Model Runner — [HF MolmoWeb-4B](https://huggingface.co/allenai/MolmoWeb-4B), [HF MolmoWeb-8B](https://huggingface.co/allenai/MolmoWeb-8B)
- The repo README gives no hardware or VRAM requirement and does not mention Mac, MPS or Apple Silicon — [GitHub README](https://raw.githubusercontent.com/allenai/molmoweb/main/README.md)
- HF backend picks `cuda` if available, else `cpu`, and loads at `torch.float32`; the native backend defaults to `cuda:0`; there is no MPS branch and no quantised loading path — [agent/model_backends.py](https://github.com/allenai/molmoweb/blob/main/agent/model_backends.py)
- vLLM is not officially supported; README warns vLLM lacks the exact attention backend used in OLMo; a maintainer posted a `VLLMActionPredictor` class (needs vllm>=0.15.0, with a monkey patch) on 26 May 2026 with the ±10% caveat — [GitHub README](https://raw.githubusercontent.com/allenai/molmoweb/main/README.md), [GitHub issue #17](https://github.com/allenai/molmoweb/issues/17)
- Apple Silicon report (Mac Studio M4 Max, 128 GB, macOS 26.4, both sizes, HF checkpoints; opened 8 April 2026): MPS inference crashed because float64 tensors are created; headless Playwright `page.screenshot()` hung at the first step and timed out after 30 s; a missing `import os`. The reporter's local fixes: auto-detect `mps` and force float32, add `--disable-gpu`, CDP screenshot fallback. A maintainer asked for a PR; the issue was closed as completed on 28 October 2026 — [GitHub issue #11](https://github.com/allenai/molmoweb/issues/11)
- The current `browser_env.py` does contain a CDP `Page.captureScreenshot` fallback — [utils/envs/browser_env.py](https://github.com/allenai/molmoweb/blob/main/utils/envs/browser_env.py); the current `model_backends.py` still has no `mps` device selection — [agent/model_backends.py](https://github.com/allenai/molmoweb/blob/main/agent/model_backends.py)
- Community MLX build: ravilution/MolmoWeb-8B-8bit, MLX 8-bit, 12.9 GB, run with `mlx-vlm`; README is empty, no hardware, speed or accuracy data, 33 downloads last month — [HF ravilution/MolmoWeb-8B-8bit](https://huggingface.co/ravilution/MolmoWeb-8B-8bit)
- Community 8-bit build: beaupi/MolmoWeb-8B-oQ8, tagged 8-bit, card text copied from Ai2's, 25 downloads last month; format and method not documented — [HF beaupi/MolmoWeb-8B-oQ8](https://huggingface.co/beaupi/MolmoWeb-8B-oQ8)
- Other community repos in the search (17 total) are fine-tunes, not quantisations: six `XunmeiLiu/molmoweb-4b-*` RL-style checkpoints (June 2026), `ravilution/MolmoWeb-4B`, a 450M `LFM2.5-VL-450M-MolmoWeb-SFT` trained on the data; none is tagged GGUF — [HF model search](https://huggingface.co/models?search=molmoweb)
- A web search for "MolmoWeb GGUF OR MLX quantized" surfaced no GGUF build and no Ollama or LM Studio listing — [HF model search](https://huggingface.co/models?search=molmoweb)
- Adoption signal: about 1.7k downloads last month for the 4B and about 760 for the 8B — [HF model search](https://huggingface.co/models?search=molmoweb)
- The paper reports no latency or throughput numbers and lists "not optimized for latency" as a limitation; evaluation allowed up to 100 steps per task; repo benchmark default is 30 steps, client default 15 — [arXiv HTML](https://arxiv.org/html/2604.08516v1), [GitHub README](https://raw.githubusercontent.com/allenai/molmoweb/main/README.md), [inference/client.py](https://github.com/allenai/molmoweb/blob/main/inference/client.py)

### Inferences
- Memory, by arithmetic rather than a published figure: float32 weights are about 4 bytes per parameter, so roughly 20 GB for the 4B (5B params) and 36 GB for the 8B (9B params) before activations; half that in bf16/fp16 (about 10 GB and 18 GB); the one 8-bit MLX file is 12.9 GB for the 8B. A 4-bit build of the 4B would be about 3–4 GB, but none is published and none has been validated.
- GGUF/llama.cpp/Ollama/LM Studio are unlikely to appear soon: Molmo2 uses custom code (`trust_remote_code`), a multi-crop image preprocessor and a specific attention path, and Ai2 warns that even vLLM diverges. Quantisation effects on click-coordinate accuracy are untested in public; given the reported sensitivity to attention-backend differences, heavy quantisation is a real risk for an agent that emits coordinates to two decimals.
- On a Mac the practical routes are (a) the reference PyTorch server on MPS with the float32 patch from issue #11, needing a 32–64 GB machine for the 8B at full precision, or (b) the community MLX 8-bit build via `mlx-vlm` with a custom harness. Both are unsupported.
- The MPS half of issue #11 does not appear to be merged (no `mps` in the backend file today), despite the issue being closed as completed.

### Gaps
- No published tokens-per-second, seconds-per-step, or average steps-per-task figures anywhere (paper, card, repo, issues).
- No measured RAM/VRAM numbers from Ai2 or users.
- No Reddit r/LocalLLaMA or Hacker News thread with hands-on local results surfaced in search; their absence from search results does not prove none exist.
- Whether `mlx-vlm` officially supports the Molmo2 architecture, and from which version, was not checked.

## 5. Safety behaviour: approval points, refusals, prompt injection, restrictions

### Takeaway
The model and the open-source harness have no built-in safety layer: no stop-for-approval step, no refusal training described, no prompt-injection defence. All published guardrails (site whitelist, query moderation, blocking password and card fields) live in Ai2's hosted demo only, and the model was deliberately not trained on login or payment tasks.

### Cited Findings
- Hosted demo safeguards: restricted to whitelisted websites; Google Cloud Natural Language API flags and rejects unsafe queries; checks input field types before typing and blocks actions on password and credit-card fields. Ai2 states these apply to the demo, not the model — [Ai2 blog](https://allenai.org/blog/molmoweb)
- The model was not trained on tasks requiring logins or financial transactions — [Ai2 blog](https://allenai.org/blog/molmoweb); repeated in [VentureBeat](https://venturebeat.com/data/ai2-releases-molmoweb-an-open-weight-visual-web-agent-with-30k-human-task) and [The Decoder](https://the-decoder.com/ai2s-fully-open-web-agent-molmoweb-navigates-the-web-using-only-screenshots/)
- The paper has no dedicated safety section; safety guardrails are mentioned only for the public demo in author contributions — [arXiv HTML](https://arxiv.org/html/2604.08516v1)
- Model card: use governed by Ai2's Responsible Use Guidelines; no safety evaluation described — [HF MolmoWeb-8B](https://huggingface.co/allenai/MolmoWeb-8B)
- A grep of the repo's `utils/envs/browser_env.py`, `utils/envs/action_executor.py`, `inference/client.py`, `agent/model_backends.py` and `agent/actions.py` for password / credit / whitelist / allowlist / confirm / safety / sensitive returned no matches, i.e. the demo's guardrails are not in the released harness — [GitHub allenai/molmoweb](https://github.com/allenai/molmoweb)
- The action set includes `send_msg_to_user` and, in code, `report_infeasible`, which are the only ways the agent hands control back — [arXiv HTML](https://arxiv.org/html/2604.08516v1), [agent/actions.py](https://github.com/allenai/molmoweb/blob/main/agent/actions.py)
- The local environment launches Chromium with `--disable-blink-features=AutomationControlled` ("STEALTH_ARGS"), and the Browserbase environment waits for Browserbase's CAPTCHA solving before proceeding — [utils/envs/browser_env.py](https://github.com/allenai/molmoweb/blob/main/utils/envs/browser_env.py)
- The Decoder lists as unresolved: how agents should treat sites' terms of service, how to prevent access to illegal content, and how to prevent irreversible actions — [The Decoder](https://the-decoder.com/ai2s-fully-open-web-agent-molmoweb-navigates-the-web-using-only-screenshots/)

### Inferences
- For a user driving their own logged-in browser, every guardrail must be built in the harness: confirm-before-submit, domain allowlists, field-type checks, and injection screening. Nothing indicates MolmoWeb was trained to pause at "critical points" or to distrust on-page instructions, and a screenshot-only model reads injected page text as part of its only observation.
- "Not trained on logins or payments" is both a safety property and a capability gap: behaviour inside authenticated sessions (webmail, banking, checkout) is out of distribution and untested.
- The stealth flag and CAPTCHA-solver integration show the harness is tuned for benchmark throughput on the public web rather than for cautious operation.

### Gaps
- No published prompt-injection or adversarial-robustness evaluation of MolmoWeb was found.
- No statement on whether the model ever refuses harmful tasks by itself.
- Ai2 Responsible Use Guidelines text not read.

## 6. Known weaknesses and criticisms

### Takeaway
Ai2's own list is candid: weak reading of small text, trouble with ambiguous or heavily constrained tasks and search filters, rare use of in-element scroll, hover and drag-and-drop, thought/action mismatches, and getting stuck repeating an action. Community evidence is thin and mostly about setup friction and backend sensitivity rather than task quality.

### Cited Findings
- Paper Sec. 6 limitations: works best with specific instructions; struggles with ambiguous tasks, many constraints, or search filters; weak OCR on small text and complex reading comprehension; not optimised for latency; thoughts sometimes do not match actions; rarely uses infrequent actions (scroll_at, drag-and-drop, hover); can get stuck repeating the same action without recovering — [arXiv HTML](https://arxiv.org/html/2604.08516v1)
- Blog limitations: errors reading text from screenshots; can be derailed by early actions such as scrolling before a page finishes loading; performance drops with ambiguous or highly constrained instructions; struggles with scrolling inside specific page elements and with drag-and-drop — [Ai2 blog](https://allenai.org/blog/molmoweb)
- GitHub issues (10 total, 2 open as of 12 Nov 2026), titles only: #1 "Incorrect success reporting in simple click sequence task" (Mar 2026); #2 "Coordinate Drift/Shift during Inference (MolmoWeb-4B Base Model)" (Mar 2026); #8 unable to produce a right-click `mouse_click(..., button='right')` (Apr 2026); #11 Apple Silicon and Playwright stability; #17 vLLM support; #20 annotation browser app fails to start; #28 region-dependent sites cause run-to-run instability (open, Oct 2026) — [GitHub issues list](https://github.com/allenai/molmoweb/issues?q=is%3Aissue)
- HF 8B discussions: an open WIP PR "Fix HF inference to match native MolmoWeb outputs exactly" and an installation video thread; nothing on quantisation, VRAM or speed — [HF MolmoWeb-8B discussions](https://huggingface.co/allenai/MolmoWeb-8B/discussions)
- Backend sensitivity: small logit differences between vLLM, HF/transformers and Molmo-native "compound across tokens and steps", up to ±10% end-task variation — [GitHub issue #17](https://github.com/allenai/molmoweb/issues/17)
- Screenshot-only cost: trails its Gemini-based AxTree teacher by five points — [The Decoder](https://the-decoder.com/ai2s-fully-open-web-agent-molmoweb-navigates-the-web-using-only-screenshots/) (unverified (secondary))
- Press coverage (VentureBeat, The Decoder) contains no outside analyst criticism; the limitations quoted are Ai2's own — [VentureBeat](https://venturebeat.com/data/ai2-releases-molmoweb-an-open-weight-visual-web-agent-with-30k-human-task), [The Decoder](https://the-decoder.com/ai2s-fully-open-web-agent-molmoweb-navigates-the-web-using-only-screenshots/)
- Data-quality observation from the paper as relayed by The Decoder: synthetic runs taught the model better than human demonstrations on identical tasks because humans take detours on unfamiliar sites; 10% of the data gives 85–90% of final performance — [The Decoder](https://the-decoder.com/ai2s-fully-open-web-agent-molmoweb-navigates-the-web-using-only-screenshots/) (unverified (secondary))

### Inferences
- The combination "weak small-text OCR + one screenshot per step + text-only memory" makes MolmoWeb a poor fit for text-heavy reading tasks (long articles, dense tables, email triage); it is strongest at navigation and form-style tasks with explicit instructions.
- "Gets stuck repeating an action" plus sampled decoding means a local harness needs loop detection and a step cap; the paper's own answer is several short parallel rollouts rather than one long one.
- No right-click and rare hover/drag use limits it on apps that depend on context menus or drag interactions.
- The need for exact-backend fidelity (native vs HF vs vLLM) is unusual and is itself a weakness for local deployment, where quantised or alternative runtimes are the norm.

### Gaps
- Issue bodies for #1, #2, #8 and #28 were not read; only titles and comment counts.
- No r/LocalLLaMA or Hacker News discussion with real-world reports was found via search; community signal is limited to GitHub and Hugging Face.
- No independent failure analysis (blog or paper by a third party) was found.

## 7. Released training data and why it matters for fine-tuning

### Takeaway
Ai2 released the whole training mix (MolmoWebMix): about 36K human task trajectories, about 105K–108K synthetic trajectories, 116K human skill segments, plus millions of grounding and screenshot-QA examples, together with the training code, the pretrained starting checkpoints and the Chrome-extension recording tool. That makes MolmoWeb unusually easy to fine-tune on your own sites or logged-in workflows.

### Cited Findings
- Paper Table 2: MolmoWebMix-Traj totals 278.5K trajectories and 2.2M steps. Synthetic: AxTree single-agent 70K, multi-agent 35K, atomic skills 5.5K, node-traversal 16K. Human: 36K trajectories (623K steps) and 116K human skill segments — [arXiv HTML](https://arxiv.org/html/2604.08516v1)
- MolmoWebMix-Perception: 10.5M steps; PixMoPoints + SyntheticGround 8.3M; ScreenshotQA 2,237,252 pairs across 395 websites; grounding QA over 7M pairs (3.4M templated, 3.8M GPT-5-generated) plus 1.1M PixMoPoints examples — [arXiv HTML](https://arxiv.org/html/2604.08516v1)
- Model card dataset sizes: MolmoWeb-HumanTrajs 36k, MolmoWeb-SyntheticTrajs 108k, MolmoWeb-HumanSkills 116k — [HF MolmoWeb-8B](https://huggingface.co/allenai/MolmoWeb-8B)
- HumanTrajs dataset: 35,981 rows, 183 GB; each record has an instruction at high/mid/low levels and a per-step trajectory with screenshot, action string, action description, a `thought`, action name and parameters, URL and open-tab info, timestamp; licence ODC-BY 1.0 — [HF dataset MolmoWeb-HumanTrajs](https://huggingface.co/datasets/allenai/MolmoWeb-HumanTrajs)
- Blog: 36K human task trajectories, over 623K subtask demonstrations, across more than 1.1K websites; synthetic trajectories come from text-only accessibility-tree agents (filtered single-agent runs, multi-agent pipelines, deterministic link exploration); MolmoWeb was not trained by distilling proprietary vision-based agents — [Ai2 blog](https://allenai.org/blog/molmoweb)
- Abstract wording: "over 100K synthetic task trajectories and 30K+ human demonstrations" — [arXiv abs](https://arxiv.org/abs/2604.08516); VentureBeat's headline and body use 30,000 human trajectories and "more than 590,000" subtask demonstrations — [VentureBeat](https://venturebeat.com/data/ai2-releases-molmoweb-an-open-weight-visual-web-agent-with-30k-human-task); these are lower than the 36K / 623K in the paper table, blog and dataset.
- Synthetic pipeline detail: Gemini 2.5 Flash planner, an operator, and a GPT-4o verifier — [The Decoder](https://the-decoder.com/ai2s-fully-open-web-agent-molmoweb-navigates-the-web-using-only-screenshots/) (unverified (secondary))
- Training recipe: supervised fine-tuning only (no RL), 64 H100 GPUs, global batch 128, up to 50K steps (about 3.2 epochs) — [arXiv HTML](https://arxiv.org/html/2604.08516v1)
- Repo ships `train/` (single-stage SFT from the MolmoWeb-Pretrained checkpoints; launch default 8 GPUs), dataset download scripts, and `annotation/` containing the Chrome extension (side panel, event collector) used to record human demonstrations — [GitHub README](https://raw.githubusercontent.com/allenai/molmoweb/main/README.md), [GitHub API tree](https://api.github.com/repos/allenai/molmoweb/git/trees/main?recursive=1)
- Evidence that others do fine-tune from it: six `XunmeiLiu/molmoweb-4b-*` checkpoints and a 450M LFM2.5-VL model trained on MolmoWeb data are on the Hub — [HF model search](https://huggingface.co/models?search=molmoweb)

### Inferences
- The human-demonstration count to quote is 36K trajectories (35,981 rows); "30K" is the rounded-down launch figure. The 108K synthetic figure on the card versus 105K (70K + 35K) in the paper table probably differs by which sub-sets are bundled into the SyntheticTrajs repo.
- Why it matters: with the recording extension, the data format, the SFT code and the pretrained base all public under permissive terms, a user can record a few hundred of their own trajectories (including the logged-in flows Ai2 excluded) and fine-tune the 4B. The "10% of data gives 85–90% of performance" finding, if accurate, suggests small targeted additions are worthwhile.
- The cost side: the reference recipe is 64 H100s and the tooling assumes multi-GPU CUDA; there is no LoRA or Apple Silicon training path documented, so practical fine-tuning means rented GPUs.
- Because trajectories include thoughts and three instruction granularities, the data is also reusable for training other small VLM agents, as the 450M community model shows.

### Gaps
- Licences of the five sibling datasets (SyntheticTrajs, HumanSkills, SyntheticSkills, SyntheticQA, SyntheticGround) were not individually confirmed.
- No documented LoRA/PEFT recipe or single-GPU fine-tuning cost was found.
- The "synthetic beats human per example" and "10% of data" claims were seen only via The Decoder; the paper section was not located in my read.
