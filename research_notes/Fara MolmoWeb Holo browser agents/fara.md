# Microsoft Fara family (Fara-7B, Fara1.5-4B/9B/27B) — open-weight browser agents, state as of November 2026

Source reliability key used below: **[primary]** = Microsoft model card, Microsoft repo, Microsoft Research page or arXiv paper read directly; **[community]** = third-party repo or issue read directly; **[unverified]** = seen only in a search-result summary or aggregator, not opened and confirmed.

## 1. Sizes, base models, licences, and whether Fara1.5 is really released

### Takeaway
Fara-7B (24 Nov 2025) is a fine-tune of Qwen2.5-VL-7B; Fara1.5 (announced 21 May 2026) is a three-size family (4B, 9B, 27B) fine-tuned from Qwen3.5, and its weights are genuinely downloadable from Hugging Face. Everything (both generations' weights, the microsoft/fara harness code, and MagenticLite/Magentic-UI) is MIT-licensed.

### Cited Findings
- Fara-7B: licence MIT; base model Qwen2.5-VL (7B), which is Apache-2.0; 7B parameters (the safetensors metadata on the card shows "8B params"); released 24 Nov 2025; trained 26–29 Oct 2025 on 64 H100s for about 2.5 days. [primary] — [HF microsoft/Fara-7B](https://huggingface.co/microsoft/Fara-7B)
- The Fara-7B card now carries a notice that Microsoft has since released Fara1.5 in 4B, 9B and 27B sizes, described as a substantial improvement. [primary] — [HF microsoft/Fara-7B](https://huggingface.co/microsoft/Fara-7B)
- Fara1.5-9B: licence MIT; model tree lists Qwen/Qwen3.5-9B-Base as base and Qwen/Qwen3.5-9B as the direct fine-tune parent; 9B parameters in BF16; release date in model details 21 May 2026; developer Microsoft Research AI Frontiers; context length 262,144 tokens. [primary] — [HF microsoft/Fara1.5-9B](https://huggingface.co/microsoft/Fara1.5-9B)
- Fara1.5-27B: licence MIT; "supervised fine-tuned from Qwen3.5-27B"; 27B parameters in BF16; release date 21 May 2026; context 262,144. [primary] — [HF microsoft/Fara1.5-27B](https://huggingface.co/microsoft/Fara1.5-27B)
- Microsoft Research's Fara1.5 article was published 21 May 2026 and carries a dated update: "Fara1.5 weights are now publicly available on HuggingFace under the MIT license!" dated 22 July 2026. It describes Fara1.5 as "a research preview". [primary] — [MSR: Fara1.5 computer-use agent](https://www.microsoft.com/en-us/research/articles/fara1-5-computer-use-agent)
- The Fara1.5 paper is arXiv 2606.20785, "Fara-1.5: Scalable Learning Environments for Computer Use Agents" (Awadallah, Gupta, Lara, Lu, Mozannar, Nambi, Nussbaum, Pandya, Rajeswaran, Rosset, Taymanov, do Valle, Vineet, Whitehead, Zhao); v1 submitted 18 June 2026, v2 22 July 2026. Abstract states the models are built on Qwen3.5 at 4B/9B/27B and weights are released under MIT. [primary] — [arXiv 2606.20785](https://arxiv.org/abs/2606.20785)
- The Fara-7B paper is arXiv 2511.19663, "Fara-7B: An Efficient Agentic Model for Computer Use", submitted 24 Nov 2025. [primary] — [arXiv 2511.19663](https://arxiv.org/abs/2511.19663)
- microsoft/fara repo: MIT licence (sidebar and LICENSE file); README now leads with the Fara1.5 family (4B/9B/27B, built on Qwen3.5, weights on Hugging Face, hosted on Microsoft Foundry) and keeps Fara-7B as "previous generation" behind a `--fara-7b` CLI flag. [primary] — [github.com/microsoft/fara](https://github.com/microsoft/fara)
- microsoft/magentic-ui repo (now the MagenticLite project; the older frontier-model release lives on the `magentic-ui-0.1` branch): code under MIT. [primary] — [github.com/microsoft/magentic-ui](https://github.com/microsoft/magentic-ui)
- Hosted availability at launch: the MSR article says Microsoft Foundry hosts Fara1.5-9B and that 9B is the one integrated with MagenticLite; the repo README (later) says all three sizes are hosted on Foundry. [primary] — [MSR article](https://www.microsoft.com/en-us/research/articles/fara1-5-computer-use-agent); [github.com/microsoft/fara](https://github.com/microsoft/fara)
- Microsoft calls 9B the flagship recommended for most uses. [primary] — [MSR blog: MagenticLite, MagenticBrain, Fara1.5](https://www.microsoft.com/en-us/research/blog/magenticlite-magenticbrain-fara1-5-an-agentic-experience-optimized-for-small-models/)

### Inferences
- "Reported released May 2026" is half right: the family was announced, hosted on Foundry and documented on 21 May 2026, but the open weights on Hugging Face appear to have landed around 17–22 July 2026 (the MSR update is dated 22 July; arXiv v2 the same day). The model cards still print 21 May 2026 as the release date.
- All three Fara1.5 sizes sit under the 32B ceiling; 27B is the largest.
- Licence position is as clean as it gets for a local user: MIT weights, MIT harness, on an Apache-2.0 (Qwen2.5-VL) base for Fara-7B. I did not open the Qwen3.5 base licence itself.

### Gaps
- I did not open the HF card for Fara1.5-4B directly; its existence, MIT licence and numbers come from the 9B/27B cards, the repo README and the paper, which all list it.
- An aggregator lists the 4B as released 17 July 2026 [unverified — [benchlm.ai](https://benchlm.ai/models/fara1-5-4b)]; exact HF upload dates were not confirmed from commit history.
- Qwen3.5 base-model licence not checked from its own card.

## 2. Inputs, outputs, action space, harness, and attaching to an existing logged-in Chrome

### Takeaway
Both generations are pure-vision agents: screenshots plus text history in, a thought block plus one coordinate-level tool call out; no DOM or accessibility tree at inference. They are meant to run inside Microsoft's own Playwright harness (`fara-cli`) or MagenticLite's sandboxed VM browser; no primary source documents attaching to a user's existing logged-in Chrome profile.

### Cited Findings
- Fara-7B input: user goal (text), current screenshot(s), and history of prior thoughts and actions as text; output: chain-of-thought block followed by a tool-call block; context 128k; screen resolution 1428x896. [primary] — [HF microsoft/Fara-7B](https://huggingface.co/microsoft/Fara-7B)
- Fara-7B action space (`computer_use` function): key, type, mouse_move, left_click, scroll, visit_url, web_search, history_back, pause_and_memorize_fact, wait, terminate. [primary] — [HF microsoft/Fara-7B](https://huggingface.co/microsoft/Fara-7B)
- Fara1.5 input/output: same shape (goal, screenshot(s), prior thoughts and actions in; chain-of-thought then an XML-tagged tool call out); most commonly trained at 1440x900 and the card recommends matching that in the sandbox. [primary] — [HF microsoft/Fara1.5-9B](https://huggingface.co/microsoft/Fara1.5-9B)
- Fara1.5 action space (larger): left_click, right_click, double_click, triple_click, mouse_move, left_click_drag, type, key, scroll, hscroll, visit_url, history_back, web_search, pause_and_memorize_fact, ask_user_question, wait, terminate. [primary] — [HF microsoft/Fara1.5-9B](https://huggingface.co/microsoft/Fara1.5-9B)
- Fara1.5 "is trained against a specific system prompt" and the card asks users to use it verbatim; the full prompt and full `computer_use` tool schema ship with MagenticLite; the card says to use the model only with the Fara CLI or Magentic-Lite harness. [primary] — [HF microsoft/Fara1.5-9B](https://huggingface.co/microsoft/Fara1.5-9B)
- The model sees the three most recent screenshots; training loss is applied to the most recent three turns. [primary] — [MSR article](https://www.microsoft.com/en-us/research/articles/fara1-5-computer-use-agent)
- The Fara-7B paper abstract describes the model as screenshot-based and predicting coordinates for actions; accessibility trees were used during data collection (by the teacher pipeline), not by the trained model, and the paper notes those trees can be unmaintained or noisy. [primary] — [arXiv 2511.19663 HTML](https://arxiv.org/html/2511.19663)
- Harness: `fara-cli --task "..." --endpoint_config <json>` with optional `--headful`, `--output_folder` (saves per-step screenshots and a `data_point.json`), `--base_url/--api_key/--model`, and `--fara-7b` for the old model. Endpoint config JSON has three keys: `model`, `base_url`, `api_key`. Browser automation is Playwright (`playwright install` in setup). Any non-vLLM host needs context of at least 15,000 tokens and temperature 0. [primary] — [github.com/microsoft/fara](https://github.com/microsoft/fara)
- The repo README covers Linux and Windows (WSL2 "highly recommended"); it does not mention macOS for `fara-cli`. MagenticLite's quick start is for "macOS or Windows (WSL)". [primary] — [github.com/microsoft/fara](https://github.com/microsoft/fara); [github.com/microsoft/magentic-ui](https://github.com/microsoft/magentic-ui)
- MagenticLite (next generation of Magentic-UI, published 21 May 2026) pairs Fara1.5 with MagenticBrain, a 14B orchestration model; browser sessions and code execution run inside Quicksand, described as a QEMU-based sandbox isolated from the host; users can watch the live browser, pause/resume, and take direct control. [primary] — [MSR blog: MagenticLite](https://www.microsoft.com/en-us/research/blog/magenticlite-magenticbrain-fara1-5-an-agentic-experience-optimized-for-small-models/); [github.com/microsoft/magentic-ui](https://github.com/microsoft/magentic-ui)
- Neither the fara README nor the magentic-ui README mentions persistent user-data directories, an existing Chrome profile, connecting over CDP, or cookie/storage-state import. [primary, absence noted] — [github.com/microsoft/fara](https://github.com/microsoft/fara); [github.com/microsoft/magentic-ui](https://github.com/microsoft/magentic-ui)
- Both model cards recommend a sandboxed browser with domain allow-lists, monitoring and a pause control, and place unsandboxed deployments out of scope. [primary] — [HF microsoft/Fara1.5-27B](https://huggingface.co/microsoft/Fara1.5-27B)

### Inferences
- Driving "my own logged-in Chrome" is against the grain of the official tooling: Microsoft's supported paths are a fresh Playwright browser or a VM-sandboxed browser, and the model is trained to stop at sign-in. It is technically plausible to modify the MIT-licensed Playwright harness to connect to a running Chrome (Playwright in general supports CDP connection), but that is my inference from general Playwright knowledge, not something a Fara source documents or supports.
- Because the model is screenshot-only with coordinate output, it is in principle harness-agnostic (anything that can screenshot at about 1440x900 and replay clicks/keys), but the trained-in system prompt and tool schema mean a custom harness must copy MagenticLite's prompt exactly.
- Logins in practice are a human-in-the-loop step: the model pauses, and MagenticLite's take-over control is how the user signs in.

### Gaps
- No primary source confirms or rules out attaching to an existing Chrome profile; the detailed fara-cli options and MagenticLite Installation/Model Hosting guides were not read.
- Whether MagenticLite can persist a logged-in session between runs inside Quicksand was not found.

## 3. Benchmark results, who ran them, judges, and verification of the specific claims

### Takeaway
All headline numbers are Microsoft self-reported, LLM-judged, and averaged over three runs: Fara-7B 73.5 WebVoyager / 34.1 Online-Mind2Web; Fara1.5-9B 86.6 / 63.4; Fara1.5-27B 89.3 / 72.3. The four claims to verify are all confirmed (72.3, 63.4, 73.5, 34.1), but the only human-verified data point anywhere is Browserbase's 62% for Fara-7B on WebVoyager, about 11 points below the auto-judge figure, and I found no independent verification of any Fara1.5 number.

### Cited Findings

**Claim checks**
- Fara1.5-27B Online-Mind2Web 72%: CONFIRMED as 72.3. [primary] — [HF microsoft/Fara1.5-27B](https://huggingface.co/microsoft/Fara1.5-27B); [arXiv 2606.20785](https://arxiv.org/abs/2606.20785)
- Fara1.5-9B Online-Mind2Web 63%: CONFIRMED as 63.4. [primary] — [HF microsoft/Fara1.5-9B](https://huggingface.co/microsoft/Fara1.5-9B); [arXiv 2606.20785](https://arxiv.org/abs/2606.20785)
- Fara-7B WebVoyager about 73.5%: CONFIRMED as 73.5. Fara-7B Online-Mind2Web "about 34–35%": the primary figure is 34.1 (the 35.3 in Microsoft's tables is MolmoWeb-8B, not Fara). [primary] — [HF microsoft/Fara-7B](https://huggingface.co/microsoft/Fara-7B); [github.com/microsoft/fara](https://github.com/microsoft/fara)

**Fara-7B (Microsoft self-reported, averaged over 3 runs)**

| Model | WebVoyager | Online-Mind2Web | DeepShop | WebTailBench (v1) |
|---|---|---|---|---|
| Fara-7B | 73.5 | 34.1 | 26.2 | 38.4 |
| UI-TARS-1.5-7B | 66.4 | 31.3 | 11.6 | 19.5 |
| GLM-4.1V-9B-Thinking | 66.8 | 33.9 | 32.0 | 22.4 |
| OpenAI computer-use-preview | 70.9 | 42.9 | 24.7 | 25.7 |
| SoM Agent (GPT-4o) | 65.1 | 34.6 | 16.0 | 30.8 |
| SoM Agent (o3) | 79.3 | 55.4 | 49.7 | 52.7 |
| SoM Agent (GPT-5) | 90.6 | 57.7 | 49.1 | 60.4 |

- Table source. [primary] — [HF microsoft/Fara-7B](https://huggingface.co/microsoft/Fara-7B)
- Fara-7B eval method: judges were GPT-4o with the official prompts for WebVoyager and DeepShop, and o4-mini for Online-Mind2Web and WebTailBench; three independent runs averaged; 100-step cap; up to five retries only after environment errors; unfinished tasks count as wrong; Browserbase hosted the browser sessions; about 48 impossible WebVoyager tasks were removed and about 50 had dates updated. [primary] — [arXiv 2511.19663 HTML](https://arxiv.org/html/2511.19663)
- Human-verified check: Browserbase (a Microsoft partner) used human annotators and scored Fara-7B at 62% on WebVoyager; the result includes retries for environment errors so it is not comparable with Browserbase's standard no-retry scores; the paper acknowledges this is lower than the GPT-4o auto-judge score. [primary] — [MSR blog: Fara-7B](https://www.microsoft.com/en-us/research/blog/fara-7b-an-efficient-agentic-model-for-computer-use/); [arXiv 2511.19663 HTML](https://arxiv.org/html/2511.19663)
- Fara-7B grounding: ScreenSpot-V1 86.7 (Qwen2.5-VL base 82.6); ScreenSpot-V2 89.3 (base 86.6). [primary] — [arXiv 2511.19663 HTML](https://arxiv.org/html/2511.19663)
- On the re-judged WebTailBench v1.5, Fara-7B falls to 48.8 process / 24.1 outcome (versus 38.4 on the original WebTailBench), so the two WebTailBench versions are not comparable. [primary] — [github.com/microsoft/fara](https://github.com/microsoft/fara)

**Fara1.5 (Microsoft self-reported, averaged over 3 runs)**

| Model | Size | WebVoyager | Online-Mind2Web | WebTailBench v1.5 process | WebTailBench v1.5 outcome |
|---|---|---|---|---|---|
| Fara-7B | 7B | 73.5 | 34.1 | 48.8 | 24.1 |
| Fara1.5-4B | 4B | 80.8 | 57.3 | 60.3 | 27.4 |
| Fara1.5-9B | 9B | 86.6 | 63.4 | 64.5 | 32.3 |
| Fara1.5-27B | 27B | 89.3 | 72.3 | 72.9 | 40.2 |
| MolmoWeb† | 8B | 78.2 | 35.3 | – | – |
| Holo2† | 8B | 80.2 | – | – | – |
| Holo2† | 30B-A3B | 83.0 | – | – | – |
| GUI-Owl-1.5† | 8B | 78.1 | 48.6 | – | – |
| GUI-Owl-1.5† | 32B | 82.0 | – | – | – |
| OpenAI Operator† | – | 87.0 | 58.3 | – | – |
| Gemini 2.5 Computer Use† | – | – | 57.3 | – | – |
| Yutori Navigator (n1)† | – | – | 64.7 | – | – |
| GPT-5 SoM | – | 90.6 | 57.7 | 69.2 | 45.1 |
| FaraGen1.5 solver (GPT-5.4), teacher upper bound | – | 93.4 | 83.4 | 79.6 | 57.4 |

- Table source; † marks numbers copied from official releases or leaderboards, not re-run by Microsoft. Fara numbers "are averaged over three independent runs". [primary] — [github.com/microsoft/fara](https://github.com/microsoft/fara)
- Fara1.5 eval method: Browserbase hosts each session, with a second pass without Browserbase for tasks that failed due to site blocking; WebVoyager judged by the GPT-4o judge of He et al. (2024); Online-Mind2Web judged by WebJudge (Xue et al., 2025) backed by o4-mini; WebTailBench v1.5 judged by a multi-stage rubric judge (GPT-5.2 and o4-mini) with a 0.8 success threshold; trajectories capped at 100 steps; `ask_user_question` calls are intercepted with a canned "continue without crossing a critical point" reply. [primary] — [arXiv 2606.20785v2 HTML](https://arxiv.org/html/2606.20785v2)
- Paper Table 7 gives Fara1.5-27B WebVoyager as 89.3 ± 1.8 (three runs, 95% CI). [primary] — [arXiv 2606.20785v2 HTML](https://arxiv.org/html/2606.20785v2)
- Discrepancy: the MSR article's table gives Fara1.5-27B WebVoyager as 88.6 and says 4B to 27B is "+7.8 points on WebVoyager"; the model card, repo and paper v2 say 89.3. [primary, conflicting] — [MSR article](https://www.microsoft.com/en-us/research/articles/fara1-5-computer-use-agent) vs [HF microsoft/Fara1.5-27B](https://huggingface.co/microsoft/Fara1.5-27B)
- Fara1.5 grounding (4B / 9B / 27B): ScreenSpot-v2 92.3 / 94.0 / 94.4; ScreenSpot-Pro with zoom 59.9 / 66.2 / 66.8 (without zoom 55.3 / 58.0 / 58.6); OSWorld-G Refined 68.0 / 69.7 / 71.3. No agentic OSWorld result is reported. [primary] — [arXiv 2606.20785v2 HTML](https://arxiv.org/html/2606.20785v2)
- Held-out synthetic environments: Fara1.5-9B averages 71.8% on six FaraEnvs versus 18.8% for Fara-7B; GPT-5.4 solver 79.4%. [primary] — [MSR article](https://www.microsoft.com/en-us/research/articles/fara1-5-computer-use-agent)
- Direct comparison statements against the other two families in this report: Microsoft's tables put MolmoWeb-8B at 78.2 WebVoyager / 35.3 Online-Mind2Web and Holo2-8B at 80.2 WebVoyager with no Online-Mind2Web score, both taken from those vendors' own releases; the paper says Fara1.5-9B beats "the next best Holo2 at 80.2" on WebVoyager. [primary] — [arXiv 2606.20785v2 HTML](https://arxiv.org/html/2606.20785v2); [MSR article](https://www.microsoft.com/en-us/research/articles/fara1-5-computer-use-agent)
- Competitor Online-Mind2Web numbers come from "automated eval results available in the official leaderboard as of May 2026". [primary] — [MSR article](https://www.microsoft.com/en-us/research/articles/fara1-5-computer-use-agent)

**Reproducibility and independent checks**
- The repo says its reproducibility pipeline "produced the previous-generation (Fara-7B) numbers" and "is being updated for the Fara1.5 evaluation stack" — Fara1.5 numbers cannot yet be reproduced from the repo docs. [primary] — [github.com/microsoft/fara](https://github.com/microsoft/fara)
- Open, unanswered issue #72 (27 Apr 2026): "Unable to reproduce Fara-7B's results on WebTailBench, even on shopping_head tasks that don't have staleness issues"; the reporter asks which judge was used (o4-mini vs GPT-5.2); no maintainer reply visible. Related open issues: #81 "Verify evals on Papers with Code" (22 Jul 2026), #90 "how to online_mind2web eval protocol" (14 Sep 2026), #71 asking for Fara-7B WebTailBench trajectories. [community] — [microsoft/fara issue #72](https://github.com/microsoft/fara/issues/72); [microsoft/fara issues](https://github.com/microsoft/fara/issues)
- Steel's leaderboard front page (last updated 11 Oct 2026) shows only the top three per benchmark and no Fara, MolmoWeb or Holo entry among them. [community] — [leaderboard.steel.dev](https://leaderboard.steel.dev/)

### Inferences
- The 88.6 vs 89.3 discrepancy for the 27B on WebVoyager is most likely the article keeping paper-v1 numbers ("+7.8" = 88.6 − 80.8) while the card and paper v2 were updated; either way the gap is inside the stated ±1.8 interval.
- Every Fara score is an LLM-judge score. The one human-audited figure (62% vs 73.5% for Fara-7B on WebVoyager) suggests auto-judged WebVoyager numbers for this family may overstate real success by roughly ten points; no equivalent human audit exists for Fara1.5, so 86.6/89.3 should be read with the same caution.
- Online-Mind2Web is the more discriminating benchmark here: Fara-7B, MolmoWeb-8B and UI-TARS all sit at 31–35, while Fara1.5-4B alone reaches 57.3, which is the family's strongest selling point at small size — but it is Microsoft's own run against competitors' self-reported numbers under possibly different harness settings (retries, Browserbase, second pass for blocked sites).
- The "retries after environment errors" and "second pass without Browserbase" policies make these numbers kinder than a single cold run from a home IP would be.
- WebTailBench is Microsoft's own benchmark, judged by Microsoft's own verifier, which is also the filter used on training data; it is best treated as an internal progress metric, not an external one.

### Gaps
- The Online-Mind2Web leaderboard Space on Hugging Face did not render for me, so I could not confirm whether Fara entries exist there or whether any are human-evaluated: [osunlp/Online_Mind2Web_Leaderboard](https://huggingface.co/spaces/osunlp/Online_Mind2Web_Leaderboard).
- Steel's full per-benchmark boards and any Browserbase leaderboard were not opened; I found no independent third-party evaluation of any Fara1.5 size.
- No DeepShop number for Fara1.5 and no agentic OSWorld number for either generation was found (the models are browser-only).
- A search summary said an Azure Labs page claims the 27B "clears 90%"; I did not open it and it conflicts with 72.3/89.3 depending on benchmark — treat as unverified: [labs.ai.azure.com](https://labs.ai.azure.com/?p=1174).

## 4. Running locally: quantised builds, memory, Apple Silicon, speed, steps and cost

### Takeaway
Microsoft only documents GPU serving (vLLM/SGLang, bf16) and Foundry hosting, but community GGUF builds exist for all three Fara1.5 sizes and MLX builds exist for Fara-7B and at least the 4B and 27B, so Apple Silicon is workable through community artefacts rather than official support. Published speed/cost data exists for Fara-7B only (about 16 steps and $0.025 per WebVoyager task); Microsoft has published no per-task latency, step counts or cost for Fara1.5.

### Cited Findings
- Official serving for Fara1.5: `vllm serve microsoft/Fara1.5-9B --dtype bfloat16 --max-model-len 262144 --limit-mm-per-prompt image=10`; SGLang and `docker model run hf.co/microsoft/Fara1.5-9B` (Docker Model Runner) also given; requires torch ≥ 2.11.0, transformers ≥ 5.2.0, vllm ≥ 0.19.1; tested on A6000, A100, H100 and B200 GPUs; no explicit memory figure. The 27B card recommends sharding across at least 2 GPUs. [primary] — [HF microsoft/Fara1.5-9B](https://huggingface.co/microsoft/Fara1.5-9B); [HF microsoft/Fara1.5-27B](https://huggingface.co/microsoft/Fara1.5-27B)
- The Fara1.5 cards link to quantisations for llama.cpp, Ollama and LM Studio but give no setup steps; MLX and Foundry Local are not mentioned. HF model tree counts: 11 quantised models for Fara1.5-9B, 7 for Fara1.5-27B, 18 for Fara-7B. [primary] — [HF microsoft/Fara1.5-9B](https://huggingface.co/microsoft/Fara1.5-9B); [HF microsoft/Fara1.5-27B](https://huggingface.co/microsoft/Fara1.5-27B); [HF microsoft/Fara-7B](https://huggingface.co/microsoft/Fara-7B)
- Fara-7B official: bf16 on vLLM recommended; torch ≥ 2.7.1, transformers ≥ 4.53.3, vllm ≥ 0.10.0; `--tensor-parallel-size 2` suggested if memory runs out. A quantised, silicon-optimised Fara-7B for Copilot+ PCs (Windows 11, NPU) is downloadable through the AI Toolkit in VS Code. [primary] — [HF microsoft/Fara-7B](https://huggingface.co/microsoft/Fara-7B); [MSR blog: Fara-7B](https://www.microsoft.com/en-us/research/blog/fara-7b-an-efficient-agentic-model-for-computer-use/)
- Foundry Local: an open feature request "Add to Microsoft Foundry Local" (#35, 28 Nov 2025) is still open; no primary source says any Fara model is in Foundry Local. [community] — [microsoft/fara issues](https://github.com/microsoft/fara/issues)
- Community GGUF, Fara1.5-9B (bartowski, MIT, 24 files): Q4_K_M 5.91 GB (marked the default choice), Q5_K_M 6.85 GB, Q6_K 7.70 GB, Q8_0 9.55 GB, bf16 17.92 GB; Ollama command `ollama run hf.co/bartowski/Fara1.5-9B-GGUF:Q4_K_M`; one-click LM Studio link; prompt format is ChatML-style with the assistant turn opening a `<think>` block. The page as fetched does not list an mmproj vision-projector file. [community] — [bartowski/Fara1.5-9B-GGUF](https://huggingface.co/bartowski/Fara1.5-9B-GGUF)
- Community GGUF, Fara1.5-27B (bartowski): Q4_K_M 17.53 GB, Q5_K_M 20.51 GB, Q6_K 23.22 GB, Q8_0 28.67 GB, bf16 53.81 GB (split); no mmproj file mentioned on the page as fetched. [community] — [bartowski/Fara1.5-27B-GGUF](https://huggingface.co/bartowski/Fara1.5-27B-GGUF)
- Community GGUF for the 4B exists (bartowski and runanywhere, with an `ollama run` Q4_K_M command) [unverified — search summary only] — [bartowski/Fara1.5-4B-GGUF](https://huggingface.co/bartowski/Fara1.5-4B-GGUF); [runanywhere/Fara1.5-4B-GGUF](https://huggingface.co/runanywhere/Fara1.5-4B-GGUF)
- llama.cpp gotcha, reported both on HF and GitHub: "Serving Fara with llama.cpp: use --reasoning-format none, or agent harnesses get empty content" (HF discussion #4 on the 27B; GitHub issue #82, 27 Jul 2026). [community] — [HF Fara1.5-27B discussions](https://huggingface.co/microsoft/Fara1.5-27B/discussions); [microsoft/fara issues](https://github.com/microsoft/fara/issues)
- GitHub issue #86 (30 Jul 2026) is titled "fara 27b gguf run good"; issue #58 (22 Feb 2026) says the "Ollama/LM Studio hosting section could use more setup detail and compatibility notes"; issue #46 (15 Dec 2025) is "Run on 16GB VRAM" (Fara-7B era). Titles only; bodies not read. [community] — [microsoft/fara issues](https://github.com/microsoft/fara/issues)
- MLX builds [unverified — search summaries, pages not opened]: mlx-community/Fara-7B-8bit (8.8 GB on disk, loads via mlx-vlm), mlx-community/Fara1.5-4B-8bit, mlx-community/Fara1.5-4B-OptiQ-4bit, runanywhere/Fara1.5-4B-mlx-4bit, tokimoa/Fara1.5-27B-MLX-4bit; a community issue also names mlx-community/Fara1.5-9B-OptiQ-4bit and mlx-community/Fara1.5-9B-8bit as planned candidates. — [mlx-community/Fara-7B-8bit](https://huggingface.co/mlx-community/Fara-7B-8bit); [mlx-community/Fara1.5-4B-8bit](https://huggingface.co/mlx-community/Fara1.5-4B-8bit); [tokimoa/Fara1.5-27B-MLX-4bit](https://huggingface.co/tokimoa/Fara1.5-27B-MLX-4bit/discussions); [Rajeev-SG/local_cua #15](https://github.com/Rajeev-SG/local_cua/issues/15)
- One independent Apple Silicon data point: a developer on an M5 Pro with 48 GB RAM ran `runanywhere/Fara1.5-4B-mlx-4bit` and recorded about 3.1 s warm action latency and about 4.1 GB resident accelerator memory, with grounding 8/8, tier-1 tasks 2/2, tier-2 2/2 and tier-3 (longer multi-step) 0/2. Tiny sample, one person, own task set; the 9B results were planned but are not on the page read. [community] — [Rajeev-SG/local_cua #15](https://github.com/Rajeev-SG/local_cua/issues/15)
- Fara-7B efficiency (Microsoft, WebVoyager): 16.5 ± 21.1 actions per task (UI-TARS-1.5-7B about 41), about 124k input and 1.1k output tokens, $0.025 per task; on WebTailBench 41.1 actions, about 343k input and 2.4k output tokens, $0.069 per task. Pricing assumption: $0.2 per 1M tokens (lowest OpenRouter price for Qwen2.5-VL-7B). [primary] — [arXiv 2511.19663 HTML](https://arxiv.org/html/2511.19663); [MSR blog: Fara-7B](https://www.microsoft.com/en-us/research/blog/fara-7b-an-efficient-agentic-model-for-computer-use/)
- Fara1.5: steps per task are only plotted (Figure 8a), with no numbers in the text; no per-task cost or latency is reported; the paper says only that the models are "practical to deploy on modest hardware"; no Apple Silicon, NPU or quantisation results. [primary] — [arXiv 2606.20785v2 HTML](https://arxiv.org/html/2606.20785v2)
- MagenticLite's blog notes small models degrade as context grows, so the harness actively manages context. [primary] — [MSR blog: MagenticLite](https://www.microsoft.com/en-us/research/blog/magenticlite-magenticbrain-fara1-5-an-agentic-experience-optimized-for-small-models/)

### Inferences
- Rough weight-only memory by size, from the file sizes above: 4B about 4 GB at 4-bit (measured 4.1 GB by the community tester); 9B about 6 GB at Q4_K_M, about 10 GB at Q8, about 18 GB at bf16; 27B about 18 GB at Q4_K_M, about 29 GB at Q8, about 54 GB at bf16. Add image-token context on top (each step carries up to three 1440x900 screenshots). On that basis the 9B fits comfortably on a 16–24 GB Mac and the 27B at 4–6 bit fits a 32–48 GB Mac; these totals are my estimates, not published requirements.
- Fara-7B's roughly 124k input tokens per 16-step task (about 7.5k tokens per step) shows the workload is prompt-heavy: on local hardware, prompt-processing speed (image tokens) will dominate latency more than generation speed.
- All published accuracy numbers are for bf16 weights on vLLM. Nobody (Microsoft or community) appears to have published benchmark accuracy for 4-bit GGUF/MLX builds, so the quantised accuracy a Mac user would actually get is unmeasured. Coordinate-precision tasks are plausibly sensitive to aggressive quantisation, but that is speculation.
- The official local story is strongest on Windows (Copilot+ NPU build of Fara-7B, WSL2) and Linux GPU; macOS support comes via MagenticLite's quick start plus community GGUF/MLX.

### Gaps
- Whether the bartowski GGUF repos include the mmproj vision projector (required for image input in llama.cpp-based runtimes) could not be confirmed from the pages as fetched; this must be checked before relying on Ollama/LM Studio for a vision-only agent.
- No official Ollama library entry, LM Studio catalogue entry or Foundry Local entry was confirmed for any Fara model.
- No tokens-per-second or seconds-per-step figures for the 9B or 27B on Apple Silicon were found.
- MagenticLite's Model Hosting Guide (which may document Ollama/LM Studio endpoints) was not read.

## 5. Safety behaviour: critical points, refusals, prompt injection, red-teaming

### Takeaway
Fara is trained to stop and ask at "critical points" (personal data, payments, sending, submitting, signing in, irreversible actions) and to refuse harmful tasks; measured refusal is 81.9% for Fara-7B and 100% for Fara1.5 on Microsoft's own 111-task set. Prompt-injection resistance is asserted qualitatively only — no attack-success numbers are published for either generation, and Microsoft itself lists injection as a known risk of vision-only perception.

### Cited Findings
- Critical point definition (Fara-7B): "any situation that requires the user's personal data or consent" before a transaction or irreversible action; the model should tell the user it cannot proceed without consent. Listed stops: entering personal information, completing purchases, making calls, sending emails, submitting applications, signing into accounts. [primary] — [MSR blog: Fara-7B](https://www.microsoft.com/en-us/research/blog/fara-7b-an-efficient-agentic-model-for-computer-use/); [HF microsoft/Fara-7B](https://huggingface.co/microsoft/Fara-7B)
- Fara1.5 critical points: trained to pause and ask for missing user information, underspecified tasks, and irreversible actions unless the user has authorised them, via the `ask_user_question` action. MagenticLite's blog says the triggers were recalibrated so they do not block useful tasks such as form-filling. [primary] — [HF microsoft/Fara1.5-9B](https://huggingface.co/microsoft/Fara1.5-9B); [MSR blog: MagenticLite](https://www.microsoft.com/en-us/research/blog/magenticlite-magenticbrain-fara1-5-an-agentic-experience-optimized-for-small-models/)
- Fara-7B refusals: 94.2% on AgentHarm-Chat and 81.9% on WebTailBench-Refusals (111 tasks, seven harm categories). [primary] — [arXiv 2511.19663 HTML](https://arxiv.org/html/2511.19663)
- Fara-7B critical-point test: on 23 tasks in REAL environments it stopped before the critical point in 19; in the other four it marked an email as read, liked a post, and published a post without confirmation. The authors call the test set small. [primary] — [arXiv 2511.19663 HTML](https://arxiv.org/html/2511.19663)
- Fara-7B adversarial test: on 13 tasks run against Magentic-UI it avoided harm in 9; the failures involved local or cached file links, which the browser sandbox blocked; it dismissed pop-ups with Escape and halted at permission and passkey dialogs. No dedicated prompt-injection benchmark is reported. [primary] — [arXiv 2511.19663 HTML](https://arxiv.org/html/2511.19663)
- Fara-7B refusal categories: illegal activity, deception, high-risk regulated domains (medical, legal, financial), harassment/exploitation/hate, unsafe technical use, misinformation, sexual content. Red-teamed on Azure for grounding, jailbreaks, harmful content and copyright; no rates on the card. [primary] — [HF microsoft/Fara-7B](https://huggingface.co/microsoft/Fara-7B)
- Fara1.5: all three sizes refuse 100% of the 111 WebTailBench-Refusals tasks; the critical-point stopping rate "remains in line with Fara-7B"; the internal red-team suite is reported qualitatively only (improves over Fara-7B on direct harmful prompts and "remains robust" to adversarial injection prompts, no figures). [primary] — [arXiv 2606.20785v2 HTML](https://arxiv.org/html/2606.20785v2)
- Fara1.5 critical-point training: a form-filling dataset of 8,505 verified trajectories (71% multi-turn); on the held-out split where the user grants permission, Fara-7B scores 0% and a model trained on this data reaches roughly 80%. [primary] — [arXiv 2606.20785v2 HTML](https://arxiv.org/html/2606.20785v2)
- Fara1.5 cards: automated red-teaming on Azure covering groundedness, jailbreak resistance, harmful content and copyright, no numbers; prompt injection listed as a known risk because vision-only perception "can be misled by deceptive page rendering, prompt injections, or ambiguous UI elements". [primary] — [HF microsoft/Fara1.5-9B](https://huggingface.co/microsoft/Fara1.5-9B)
- Operational guidance: sandboxed browser, domain allow-lists, monitoring, an immediate pause control, avoid sensitive data and high-risk domains; with MagenticLite "all actions by the agent are logged and auditable". [primary] — [github.com/microsoft/fara](https://github.com/microsoft/fara); [MSR article](https://www.microsoft.com/en-us/research/articles/fara1-5-computer-use-agent)

### Inferences
- The safety design assumes a sandbox. A user who points Fara at their real, logged-in browser removes the main mitigation Microsoft relies on (the 7B's four adversarial failures were caught by sandboxing, not by the model), while the model's injection resistance is unquantified.
- Critical-point stopping is good but not complete: 19 of 23 for Fara-7B, with the misses being low-stakes but real side effects (publishing a post). Fara1.5 is said to be "in line", which implies similar leakage.
- The Fara-7B paper notes the model never saw training data beyond critical points, so behaviour after a user says "go ahead" was undefined for 7B (0% on the permission-granted split); Fara1.5 fixes this specifically.
- In benchmark runs the harness auto-answers `ask_user_question`; real use will involve more interruptions than the benchmark step counts suggest.

### Gaps
- No published prompt-injection attack-success rate, no third-party red-team report, and no numeric critical-point adherence figure for Fara1.5 were found.
- The repo's TRANSPARENCY_NOTE.md was not read.

## 6. Known weaknesses, criticisms and community reports

### Takeaway
Microsoft's own failure analysis shows the 27B's failures are dominated by execution/strategy errors and hallucination, with success dropping as trajectories lengthen; both generations are English-only, browser-only research previews. Community signal is thin and mostly about hosting friction and reproducibility rather than quality; I found no substantial Reddit or Hacker News thread.

### Cited Findings
- Fara1.5 card limitations: vision-only perception can be misled; errors accumulate across multi-step trajectories; "run-to-run variance on multi-turn tasks is non-trivial"; it can hallucinate page state or misattribute information from earlier screenshots; English only; out of scope for legal/health/financial advice and unsandboxed deployment. [primary] — [HF microsoft/Fara1.5-9B](https://huggingface.co/microsoft/Fara1.5-9B); [HF microsoft/Fara1.5-27B](https://huggingface.co/microsoft/Fara1.5-27B)
- Fara1.5-27B failure analysis (paper Appendix A.7; categories overlap so do not sum to 100). WebVoyager failures: Execution & Strategy 66.6%, Hallucination 37.8%, Tool Interaction 18.5%, Selection 18.3%, Critical Point 0.1%. Online-Mind2Web: Execution & Strategy 79.2%, Hallucination 52.2%, Tool Interaction 32.2%, Selection 29.4%, Critical Point 0.8%. WebTailBench v1.5: Execution & Strategy 78.0%, Hallucination 56.5%, Selection 36.5%, Tool Interaction 32.5%, Critical Point 0.7%. Environment failures: 2.7% (WebVoyager), 3.5% (Online-Mind2Web), 7.8% (WebTailBench v1.5). [primary] — [arXiv 2606.20785v2 HTML](https://arxiv.org/html/2606.20785v2)
- Success declines as trajectories get longer, more so on harder benchmarks; there is distribution shift between sandboxed replicas and live sites (layout, ads, latency, dynamic content). [primary] — [arXiv 2606.20785v2 HTML](https://arxiv.org/html/2606.20785v2)
- Ceiling: "there is still a small gap in performance between Fara1.5 and the 'teacher'" (GPT-5.4 solver: 93.4 WebVoyager, 83.4 Online-Mind2Web), which bounds the supervised-fine-tuning recipe; scope is browser tasks only, with desktop, enterprise software and terminal use listed as future work. [primary] — [MSR article](https://www.microsoft.com/en-us/research/articles/fara1-5-computer-use-agent)
- Outcome vs process gap: on WebTailBench v1.5 the 27B follows a sound process 72.9% of the time but gets the right outcome only 40.2% (9B: 64.5 vs 32.3; 4B: 60.3 vs 27.4). [primary] — [github.com/microsoft/fara](https://github.com/microsoft/fara)
- Fara-7B stated limitations: "challenges with accuracy on more complex tasks", mistakes in following instructions, susceptibility to hallucinations; experimental preview; multi-turn extensions were a small share of training data; low real-estate scores may reflect anti-bot defences on those sites; the training verifier agrees with humans 83.3% of the time (16.7% false positive, 18.4% false negative). [primary] — [MSR blog: Fara-7B](https://www.microsoft.com/en-us/research/blog/fara-7b-an-efficient-agentic-model-for-computer-use/); [arXiv 2511.19663 HTML](https://arxiv.org/html/2511.19663)
- Logins and paywalls: the Fara-7B task-proposal stage excluded tasks requiring logins or paywall bypasses, and the model is trained to stop at sign-in. [primary] — [arXiv 2511.19663 HTML](https://arxiv.org/html/2511.19663)
- Anti-bot blocking is handled in evaluation by infrastructure, not the model: Browserbase "to stabilize browser sessions", retries on environment errors, and a second pass without Browserbase for blocked sites. [primary] — [arXiv 2606.20785v2 HTML](https://arxiv.org/html/2606.20785v2)
- GitHub issue tracker (28 open issues as of fetch): recurring themes are vLLM install/serve failures (#28, #29, #33, #57), hosting on consumer hardware (#46 16 GB VRAM, #58 Ollama/LM Studio docs, #82 llama.cpp flag), eval reproducibility (#72, #81, #90, #56, #49), a hard-coded max-rounds bug (#59 "Max rounds is currently hardcoded so argument doesn't apply"), fine-tuning how-to requests (#22, #75), and #85 "does it support computer use scenairo?" (desktop). Many are open with no visible maintainer reply. [community] — [microsoft/fara issues](https://github.com/microsoft/fara/issues)
- HF discussions on Fara1.5-27B: five open threads (demo request, install video, the llama.cpp `--reasoning-format none` workaround, and two off-topic); nothing on quality failures. [community] — [HF Fara1.5-27B discussions](https://huggingface.co/microsoft/Fara1.5-27B/discussions)
- Independent local test (one developer, 4B MLX 4-bit on M5 Pro): passes grounding and short tasks, fails both longer tier-3 tasks (0/2). [community] — [Rajeev-SG/local_cua #15](https://github.com/Rajeev-SG/local_cua/issues/15)

### Inferences
- The dominant failure class (execution and strategy, plus hallucinated page state) is exactly what bites on long, real errands; combined with the paper's own "success declines with length" and the community 0/2 on longer tasks for the 4B, the family looks reliable for short, bounded web tasks and unreliable for long multi-site errands, especially at 4B/9B.
- CAPTCHA handling is effectively absent as a capability: nothing in the cards, repo or papers claims it, tasks needing logins were excluded from training proposals, and evaluation leaned on Browserbase to avoid blocks. A home user driving their own browser gets a better IP reputation and real cookies, but should expect to solve CAPTCHAs and sign-ins by hand.
- Maintainer responsiveness on GitHub looks low (issues from Nov 2025 still open), which matters for anyone depending on the harness.
- "Research preview" is repeated across every Fara1.5 primary source; Microsoft is not positioning this as a product.

### Gaps
- I found no Reddit r/LocalLLaMA or Hacker News thread with substantive user reports on Fara1.5 or Fara-7B; one extended search returned none. That is absence in my search, not proof that none exist.
- Issue bodies (other than #72) and the three issues on page 2 were not read; no reports of coordinate drift after quantisation or action loops were found, but I did not search for them exhaustively.
- No numeric success-vs-trajectory-length curve was extracted (it is a figure in the paper).

## 7. How the training data was made (FaraGen / FaraGen1.5) and whether it is released

### Takeaway
Both generations are distilled by supervised fine-tuning from synthetic trajectories produced by a multi-agent pipeline using frontier OpenAI models as the solver and LLM verifiers as the filter (about $1 per verified trajectory for Fara-7B). The benchmarks (WebTailBench, CUAVerifierBench) are released; I found no primary statement that the training trajectories or the synthetic FaraEnvs are released.

### Cited Findings
- FaraGen (Fara-7B): a synthetic data system that proposes multi-step web tasks, attempts them, and filters successful trajectories with multiple verifiers; verified trajectories cost about $0.59 (o4-mini), $1.08 (o3) or $1.00 (GPT-5) each ("approximately $1 each" in the abstract). [primary] — [arXiv 2511.19663](https://arxiv.org/abs/2511.19663); [arXiv 2511.19663 HTML](https://arxiv.org/html/2511.19663)
- Fara-7B data: 145,603 trajectories, 1,010,797 steps, 6.9 steps on average (range 3–84), 70,117 unique domains; seed URLs mainly from ClueWeb22 plus Tranco; about 67% of tasks from agent exploration of random sites and about 28% from targeted URLs; total SFT mix 1.8 million samples including grounding, refusals and screenshot QA/captioning. [primary] — [arXiv 2511.19663 HTML](https://arxiv.org/html/2511.19663)
- Data scaling for Fara-7B from 18K to 180K to 1.8M action steps gave clear gains at each step. [primary] — [arXiv 2511.19663 HTML](https://arxiv.org/html/2511.19663)
- FaraGen1.5: three components — environments (live websites plus synthetic ones), solvers (multiple models, including GPT-5.4 with custom tools replicating the Fara1.5 action space, plus a user simulator), and verifiers scoring task correctness, efficiency and critical-point adherence. [primary] — [arXiv 2606.20785](https://arxiv.org/abs/2606.20785); [MSR article](https://www.microsoft.com/en-us/research/articles/fara1-5-computer-use-agent)
- Fara1.5 training mix (about 2M samples): web trajectories 60.0%, synthetic environments 12.8%, form filling and user interactions 12.5%, grounding 8.8%, VQA 4.9%, GUI drag 0.8%, instruction following + safety 0.1%. [primary] — [MSR article](https://www.microsoft.com/en-us/research/articles/fara1-5-computer-use-agent)
- FaraEnvs: six sandboxed synthetic environments (Mail, Calendar, Stream, ML, Stay, Scheduler), built with GitHub Copilot CLI plus human iteration, to cover gated/logged-in domains the open web cannot supply; scored by a privileged-information LLM judge comparing database snapshots. [primary] — [MSR article](https://www.microsoft.com/en-us/research/articles/fara1-5-computer-use-agent)
- Solver quality: the GPT-5.4 solver scores 83% on Online-Mind2Web under automated WebJudge versus 67% for the solver used for Fara-7B. [primary] — [MSR article](https://www.microsoft.com/en-us/research/articles/fara1-5-computer-use-agent)
- Fara1.5 card: about 1 billion text tokens and under 1 billion images; data acquisition ended 20 March 2026; tasks seeded from sampled URLs and open-source seeds such as Mind2Web; training compute 32 x B200 for 4 days (9B) and about 5 days on 64 B200 (27B). [primary] — [HF microsoft/Fara1.5-9B](https://huggingface.co/microsoft/Fara1.5-9B); [arXiv 2606.20785v2 HTML](https://arxiv.org/html/2606.20785v2)
- Synthetic-to-real transfer: on four WebVoyager domains Fara1.5-9B scores 89.8 combined; a model trained on synthetic replicas only scores 83.4; baseline 73.4. [primary] — [MSR article](https://www.microsoft.com/en-us/research/articles/fara1-5-computer-use-agent)
- Released artefacts: WebTailBench (609 tasks, 11 task types; a refreshed `test_v2` split is recommended) and CUAVerifierBench (106 trajectories in the Browserbase split, 154 in the internal split, with human reviewer verdicts), plus the Universal Verifier (`MMRubricAgent`) judge code. [primary] — [github.com/microsoft/fara](https://github.com/microsoft/fara)
- Neither paper text read, nor the model cards, states that the training trajectories or FaraEnvs are released; an open issue (#71, 27 Apr 2026) asks whether even the Fara-7B WebTailBench trajectories will be released. [primary, absence noted; community] — [arXiv 2606.20785v2 HTML](https://arxiv.org/html/2606.20785v2); [microsoft/fara issues](https://github.com/microsoft/fara/issues)

### Inferences
- Fara is a distillation of frontier OpenAI agents into small Qwen backbones; its ceiling is the teacher (the GPT-5.4 solver), and its behaviour inherits the teacher pipeline's verifier errors (about 17–18% false positive/negative for the 7B-era verifier).
- Because training data is not released, the models can be used and fine-tuned under MIT but the result cannot be reproduced from scratch; the repo has open, unanswered requests for fine-tuning guidance (#22, #75).
- Training on Mind2Web-seeded tasks and on WebVoyager-domain replicas raises a mild benchmark-proximity concern for WebVoyager and Online-Mind2Web scores; the papers present replicas as a transfer experiment, and I did not find a contamination analysis.

### Gaps
- No definitive statement found on training-data or FaraEnvs release; the Hugging Face datasets pages under microsoft/ were not searched directly.
- The Fara1.5 trajectory count (as opposed to the roughly 2M sample count) was not extracted.
