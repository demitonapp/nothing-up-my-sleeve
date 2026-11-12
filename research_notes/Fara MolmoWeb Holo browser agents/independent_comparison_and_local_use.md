# Independent comparison and local use: Microsoft Fara, Ai2 MolmoWeb, H Company Holo (state at 12 November 2026)

Scope notes for the report writer:

- "Vendor" below means the organisation that trained the model. "Cited" means a number copied from another party's report, not re-run.
- The Holo line has moved past Holo3 since the brief was written: Holo3.1 (0.8B / 4B / 9B / 35B-A3B, released 2 June 2026) and Holo4 (27B and 35B-A3B, late September 2026) are on Hugging Face. They are included where they change the practical answer. — [HF search API, Hcompany repos](https://huggingface.co/Hcompany), [Holo4 announcement](https://hcompany.ai/newsroom/holo4)
- File sizes and repo lists were read directly from the Hugging Face API on 12 Nov 2026. HN threads were read through the Algolia API. Reddit could not be searched directly; see Gaps.

## 1. Which independent parties have evaluated two or more of these models on the same benchmark and harness?

### Takeaway
None was found. Every table that shows two of the three families side by side was published by one of the vendors (Ai2 or Microsoft), and in each the rival's numbers are copied from the rival's own report, not re-run. The third-party trackers (Steel, the Online-Mind2Web board as mirrored by Steel) carry no Fara or MolmoWeb rows at all, and only vendor-submitted H Company rows.

### Cited Findings

**Vendor tables that include a rival family (the closest thing to a head-to-head)**

- Ai2's MolmoWeb paper, Table 4 (success %, columns WebVoyager / Online-Mind2Web / DeepShop / WebTailBench): Holo1-7B (30 steps) 55.4 / – / – / –; UI-TARS-1.5-7B 66.4 / 31.3 / 11.6 / 19.5; Fara-7B 73.5 / 34.1 / 26.2 / 38.4; MolmoWeb-4B 75.2 / 31.3 / 35.6 / 43.8; MolmoWeb-8B 78.2 / 35.3 / 42.3 / 49.5. Rows marked * (including Fara-7B and UI-TARS-1.5-7B) are "taken from the Fara paper"; MolmoWeb rows were run by Ai2 in its own harness; the paper does not say where the Holo1-7B figure came from. — [MolmoWeb paper, arXiv 2604.08516](https://arxiv.org/html/2604.08516)
- Same paper, judges: GPT-4o with the official prompt for WebVoyager and DeepShop; o4-mini with the Online-Mind2Web judge; and the WebVoyager judge for WebTailBench "because it is unclear which judge that benchmark used". Up to 100 steps, 3–5 runs averaged, up to 10 retries per trajectory for environment errors, browser sessions on Browserbase "with some captcha-solving capability". — [MolmoWeb paper](https://arxiv.org/html/2604.08516)
- Same paper, grounding Table 8 (ScreenSpot / ScreenSpot-v2): Holo1-7B 87.4 / 89.9; Fara-7B 86.7 / 89.3; MolmoWeb-4B 87.2 / 89.5; MolmoWeb-Ground-8B 88.7 / 91.8; Qwen2.5-VL-7B 85.5 / 89.3. This is the only table found with all three families in it. Whether Ai2 re-ran the rivals is not stated. — [MolmoWeb paper](https://arxiv.org/html/2604.08516)
- Microsoft's Fara1.5 paper, Table 3 (WebVoyager / Online-Mind2Web): Fara-7B 73.5 / 34.1; MolmoWeb-8B† 78.2 / 35.3; Holo2-8B† 80.2 / –; Holo2-30B-A3B† 83.0 / –; GUI-Owl-1.5-8B† 78.1 / 48.6; Fara1.5-4B 80.8 / 57.3; Fara1.5-9B 86.6 / 63.4; Fara1.5-27B 89.3 / 72.3. † is defined as "sourced from the model's official release or leaderboard rather than re-run by us". Holo3 and later are not in the table. — [Fara-1.5 paper, arXiv 2606.20785](https://arxiv.org/html/2606.20785v2), [microsoft/fara README](https://github.com/microsoft/fara)
- Fara1.5 judges: GPT-4o judge for WebVoyager; WebJudge backed by o4-mini for Online-Mind2Web; a rubric judge using GPT-5.2 and o4-mini for WebTailBench v1.5. Fara numbers are three-run averages. — [Fara-1.5 paper](https://arxiv.org/html/2606.20785v2)
- Microsoft's own pages disagree on one figure: the blog table gives Fara1.5-27B 88.6 on WebVoyager; the model card, GitHub README and paper give 89.3. — [Microsoft Research blog](https://www.microsoft.com/en-us/research/articles/fara1-5-computer-use-agent); contradicted by [Fara1.5-9B model card](https://huggingface.co/microsoft/Fara1.5-9B)

**Third-party papers and trackers checked**

- WebChallenger (arXiv 2606.10423) lists Fara-7B at 34.1 on Online-Mind2Web, but "All other baseline results in Table 1 are taken from their original reports"; its own 51.0% is human-evaluated and uses GLM-4-32B plus Qwen2.5-VL-7B, so it is not a re-run of any of the three families. MolmoWeb and Holo do not appear. — [WebChallenger](https://arxiv.org/html/2606.10423)
- Alibaba's Wuying-Browser-Agent paper (arXiv 2608.17319) runs many models through one harness at pass@1 / 100 steps but includes none of Fara, MolmoWeb or Holo. It does give the untuned bases that Fara1.5 is built on: Qwen3.5-4B 37.6 / 20.0, Qwen3.5-9B 37.0 / 23.0, Qwen3.5-27B 55.4 / 50.0 (WebVoyager / Online-Mind2Web). — [Wuying paper](https://arxiv.org/html/2608.17319v1)
- Steel's Online-Mind2Web board (25 rows) has no Fara, MolmoWeb or Holo row. The only open-model rows are WebChallenger at 51.0% and "HAL Leaderboard baseline (best open) ~30%". — [Steel Online-Mind2Web](https://leaderboard.steel.dev/leaderboards/online-mind2web.md)
- Steel's WebVoyager board carries three H Company rows, all sourced from H Company: Surfer 2 97.1%, Surfer-H + Holo1 92.2% (arXiv 2506.02865), Runner H 0.1 67%. No Fara or MolmoWeb row was present in the portion read (first 100k of 142k characters of the full dump). — [Steel full dump](https://leaderboard.steel.dev/llms-full.txt)
- Steel says of its own rows: "Some rows are independently benchmarked and some are team-reported." — [Steel full dump](https://leaderboard.steel.dev/llms-full.txt)
- Browserbase's Stagehand evals page returned HTTP 404 on 12 Nov 2026; Steel quotes two rows from it (Stagehand + Gemini 2.5 CU 65.0%, Stagehand + Sonnet 4.5 55.0% on Online-Mind2Web), neither an open-weight model. — [Steel Online-Mind2Web](https://leaderboard.steel.dev/leaderboards/online-mind2web.md)
- H Company's Holo4 announcement compares only against Qwen and closed frontier models on OSWorld, OSWorld 2.0, ALE-CLI, AutomationBench and AndroidWorld; it gives no WebVoyager or Online-Mind2Web figure and names neither Fara nor MolmoWeb. — [Holo4 announcement](https://hcompany.ai/newsroom/holo4)
- The Holo3.1 release post likewise reports AndroidWorld and OSWorld only (35B-A3B AndroidWorld 67% → 79.3%). — [Holo3.1 HF blog](https://huggingface.co/blog/Hcompany/holo31)

**One independent reproduction attempt (single family)**

- A user who self-hosted Holo3-35B-A3B on vLLM with a simple loop in the OSWorld framework reported "I only got 23% score on OSWorld"; H Company staff replied by pointing to a new agent-loop cookbook rather than disputing the number. — [HF discussion, Holo3-35B-A3B #5](https://huggingface.co/Hcompany/Holo3-35B-A3B/discussions/5)

### Inferences
- There is no neutral ranking of Fara vs MolmoWeb vs Holo. The defensible statements are narrower: (a) on Ai2's and Microsoft's mutually-copied numbers, MolmoWeb-8B and Fara-7B are within ~1 point on Online-Mind2Web (35.3 vs 34.1) and ~5 on WebVoyager; (b) Fara1.5 claims a ~28-point jump over both on Online-Mind2Web, on Microsoft's harness only; (c) Holo has no published Online-Mind2Web number at any version, so Holo cannot be placed on the stricter web benchmark at all.
- The families do not share a benchmark after 2025: Fara and MolmoWeb report browser benchmarks; Holo3 / 3.1 / 4 report desktop and mobile benchmarks (OSWorld, AndroidWorld). Fara1.5 and MolmoWeb are browser-only; Holo is a general computer-use model.
- The Wuying base-model rows suggest most of Fara1.5's score is fine-tuning, not the Qwen3.5 base (Qwen3.5-9B 23.0 vs Fara1.5-9B 63.4 on Online-Mind2Web), but the two numbers come from different harnesses and judges, so the size of the gain is indicative only.
- Holo's WebVoyager figure swings from 55.4 (Holo1-7B, 30 steps, in Ai2's table) to 92.2 (Surfer-H + Holo1, vendor, multi-module with a validator). That is a harness effect at least as large as any between-family gap.

### Gaps
- No third party was found that ran two of the three families in one harness. Pairings with no independent comparison at all: Fara1.5 vs MolmoWeb; Fara1.5 vs Holo3 / 3.1 / 4; MolmoWeb vs any Holo newer than Holo1.
- The Online-Mind2Web leaderboard on Hugging Face (osunlp space) was not read directly; Microsoft says its comparison uses "automated eval results available in the official leaderboard as of May 2026", so MolmoWeb and GUI-Owl may be listed there. Unverified.
- The last 42k characters of Steel's full dump and its WebVoyager detail page were not read; a Fara or MolmoWeb row there cannot be ruled out.
- The origin of the Holo1-7B 55.4 figure in Ai2's table is not stated.

## 2. How comparable are the headline numbers?

### Takeaway
Poorly. WebVoyager is near its ceiling and its judge is lenient; Online-Mind2Web is stricter but scores move by ten points or more with the judge; and each vendor's protocol differs in step budget, retries, blocked-site handling and attempt count. Only same-harness, same-judge, pass@1 figures should be compared, and for these three families those exist only inside each vendor's own paper.

### Cited Findings

**WebVoyager saturation and judge leniency**

- The Online-Mind2Web paper found "a simple agent that primarily uses Google Search can already solve up to 51% of the tasks" on WebVoyager, that the benchmark "is limited to just 15 websites", and that its automatic judge has "a high false positive rate". — [An Illusion of Progress, arXiv 2504.01382](https://arxiv.org/html/2504.01382v4)
- Agreement with human judgement: WebVoyager's evaluator 73.9% (GPT-4o) and 78.7% (o4-mini); WebJudge 83.6% (GPT-4o) and 85.7% (o4-mini), with a 3.8-point success-rate gap. — [arXiv 2504.01382](https://arxiv.org/html/2504.01382v4)
- Top of Steel's WebVoyager board: 99.19% (self-reported), 98.5%, Surfer 2 97.1%. Steel calls WebVoyager "unusually sensitive to task drift, removed tasks, evaluator choice, and whether the run used the full task suite". — [Steel full dump](https://leaderboard.steel.dev/llms-full.txt)
- Task sets are edited: Ai2 used "the task set from Fara, with infeasible tasks removed" and updated stale dates; Microsoft says it refreshes "time sensitive tasks for each benchmark". — [MolmoWeb paper](https://arxiv.org/html/2604.08516), [Fara-1.5 paper](https://arxiv.org/html/2606.20785v2)

**Online-Mind2Web: human vs WebJudge vs custom judges**

- Human-evaluated results in the original paper: Operator 61.3%, Claude Computer Use 3.7 56.3%, SeeAct 30.7%, Browser Use 30.0%, Claude CU 3.5 29.0%, Agent-E 28.0%. 300 tasks, 136 sites; CAPTCHA-protected sites were filtered out at construction. — [arXiv 2504.01382](https://arxiv.org/html/2504.01382v4)
- Same agent, two judges (reported by Yutori, relayed by Steel): Navigator 78.7% human vs 64.7% WebJudge; Gemini 2.5 CU 69.0% vs 57.3%; Claude 4.0 61.0% vs 47.7%; Claude 4.5 55.0% human vs 59.3% WebJudge (direction reversed). — [Steel Online-Mind2Web](https://leaderboard.steel.dev/leaderboards/online-mind2web.md)
- Operator appears as 61.3% (human, original paper) and 58.3% (the figure Microsoft and Ai2 use). — [Steel Online-Mind2Web](https://leaderboard.steel.dev/leaderboards/online-mind2web.md), [Fara-1.5 paper](https://arxiv.org/html/2606.20785v2)
- The top row, Browser Use Cloud 97.0%, uses a custom agentic judge and is "not directly comparable" to screenshot-based judging; Steel: "Judge methodology varies across submissions". — [Steel Online-Mind2Web](https://leaderboard.steel.dev/leaderboards/online-mind2web.md)
- Same model, two harnesses: OpenAI self-reports GPT-5.4 at 93.0%; Microsoft's GPT-5.4-based FaraGen1.5 solver scores 83.4% under WebJudge in Microsoft's harness. — [Steel Online-Mind2Web](https://leaderboard.steel.dev/leaderboards/online-mind2web.md), [microsoft/fara README](https://github.com/microsoft/fara)
- All Fara, Fara1.5 and MolmoWeb Online-Mind2Web numbers are WebJudge (o4-mini) auto-eval, not human. — [Fara-1.5 paper](https://arxiv.org/html/2606.20785v2), [MolmoWeb paper](https://arxiv.org/html/2604.08516)

**pass@1 vs best-of-N, and step budgets**

- MolmoWeb-8B: 78.2% → 94.7% on WebVoyager and 35.3% → 60.5% on Online-Mind2Web going from pass@1 to pass@4 (five rollouts, an LLM judge picks the best). The paper is inconsistent about whether the pass@4 figures use 30 or 100 steps. — [MolmoWeb paper](https://arxiv.org/html/2604.08516)
- Step budget alone moves scores: Ai2's Gemini-3-flash axtree agent goes 74.4 → 85.6 on WebVoyager and 34.8 → 44.8 on Online-Mind2Web from 30 to 100 steps. Holo1-7B's row is a 30-step figure beside 100-step rows. — [MolmoWeb paper](https://arxiv.org/html/2604.08516)
- Some secondary coverage quotes MolmoWeb's 94.7 / 60.5 beside others' single-attempt figures. — [MolmoWeb abstract](https://arxiv.org/abs/2604.08516)

**Sites blocking agents**

- Microsoft: "We rely on Browserbase to stabilize browser sessions and reduce the rate of session-level blocking." Each benchmark runs in two passes; the second "re-runs only the tasks that failed due to site-blocking without Browserbase". — [Microsoft Research blog](https://www.microsoft.com/en-us/research/articles/fara1-5-computer-use-agent), [Fara-1.5 paper](https://arxiv.org/html/2606.20785v2)
- Ai2 also ran on Browserbase with captcha solving and up to 10 retries for environment errors; it notes local browsers act faster than Browserbase. — [MolmoWeb paper](https://arxiv.org/html/2604.08516)
- Microsoft: "Agentic benchmarks are evaluated against live websites whose state changes day to day, which makes reproducible comparisons difficult." — [Fara-1.5 paper](https://arxiv.org/html/2606.20785v2)

**Protocol choices that favour the home model**

- Fara1.5's harness intercepts every `ask_user_question` call and injects a canned reply, while the SoM and GPT-5.4 baselines have that tool removed; "the outcome judge treats properly stopping at a critical point as success". WebTailBench v1.5 changed the verifier so that stopping at a customer-details page can count as success, and 270 tasks were refreshed. — [Fara-1.5 paper](https://arxiv.org/html/2606.20785v2)
- WebTailBench numbers are not comparable across the two papers: Ai2 scored it with the WebVoyager judge (Fara-7B 38.4, MolmoWeb-8B 49.5); Microsoft's v1.5 rubric judge gives Fara-7B 24.1 outcome success. — [MolmoWeb paper](https://arxiv.org/html/2604.08516), [microsoft/fara README](https://github.com/microsoft/fara)
- Microsoft's public eval pipeline "produced the previous-generation (Fara-7B) numbers and is being updated for the Fara1.5 evaluation stack". The model card adds "Run-to-run variance on multi-turn tasks is non-trivial." — [microsoft/fara README](https://github.com/microsoft/fara), [Fara1.5-9B model card](https://huggingface.co/microsoft/Fara1.5-9B)
- H Company ran Holo4 in "its own harness", 2–4 runs averaged (single run for OSWorld 2.0), while the frontier rows are public figures "across different harnesses and effort levels". — [Holo4 announcement](https://hcompany.ai/newsroom/holo4)
- Microsoft published CUAVerifierBench, human labels on 106 Fara-7B Online-Mind2Web / Browserbase trajectories, to measure the judges themselves. — [microsoft/fara README](https://github.com/microsoft/fara)

### Inferences
- A sensible reading rule: treat WebVoyager differences under ~5 points as noise; treat Online-Mind2Web figures as comparable only when both are WebJudge-o4-mini, pass@1, similar step budget and similar blocked-site policy. Under that rule the only clean cross-family statement is Fara-7B ≈ MolmoWeb-8B.
- Judge choice alone moves a score by 4–14 points and can reverse an ordering (Claude 4.5 vs Gemini 2.5 CU), so a single-digit lead under WebJudge is not evidence of a real lead.
- Fara1.5's 72.3% is not yet third-party reproducible: the evaluation stack is unreleased, and the protocol counts a correct stop-and-ask as success, which the cited baselines were not scored under.
- For a user driving their own logged-in Chrome from a home IP, the Browserbase-stabilised numbers overstate nothing about blocking (a real profile is blocked less) but say nothing about login-gated flows either; neither benchmark tests those.

### Gaps
- No human-evaluated Online-Mind2Web score exists for any Fara, MolmoWeb or Holo model.
- The fraction of tasks lost to blocking, with and without Browserbase, is not published by either vendor.
- Max step budget for the Fara1.5 runs was not found in the portion of the paper read.

## 3. Local deployment: builds, memory, vision-encoder support, speed, quantisation loss

### Takeaway
Fara and Holo are easy to run locally because they are fine-tunes of Qwen VL bases that llama.cpp and MLX already handle: both have many GGUF builds with vision projectors and MLX builds. MolmoWeb is the hard one: no GGUF exists, the only MLX builds are two low-download 8-bit community uploads, and Ai2 itself warns that vLLM may reduce accuracy. No measured Apple Silicon speed and no measured quantisation-vs-grounding result was found for any of the three.

### Cited Findings

**What builds exist (Hugging Face, 12 Nov 2026)**

- Fara-7B (Qwen2.5-VL-7B base): official ONNX (`microsoft/Fara-7B-onnx`); GGUF from bartowski, mradermacher, Mungert, prithivMLmods and others; MLX `mlx-community/Fara-7B-4bit` and `-8bit`. Microsoft's README links the bartowski GGUF "for LM Studio / Ollama". — [HF model search](https://huggingface.co/models?search=Fara), [microsoft/fara README](https://github.com/microsoft/fara)
- Fara1.5 (Qwen3.5 base, MIT): GGUF with mmproj for all three sizes from bartowski (4B 8.5k, 9B 9.8k, 27B 6.1k downloads), plus DevQuasar, prithivMLmods; MLX `mlx-community/Fara1.5-{4B,9B,27B}-OptiQ-4bit` and `Fara1.5-{4B,9B}-8bit`; FP8 and AWQ builds for vLLM. Microsoft's own instructions cover only Foundry, vLLM, SGLang and Transformers. — [bartowski/Fara1.5-9B-GGUF](https://huggingface.co/bartowski/Fara1.5-9B-GGUF), [mlx-community/Fara1.5-9B-OptiQ-4bit](https://huggingface.co/mlx-community/Fara1.5-9B-OptiQ-4bit), [Fara1.5-9B model card](https://huggingface.co/microsoft/Fara1.5-9B)
- MolmoWeb (Molmo2 architecture: Qwen3 LLM + SigLIP 2; Apache 2.0): no GGUF of any kind in a Hugging Face search. MLX: `ravilution/MolmoWeb-8B-8bit` (33 downloads, empty README, tagged `molmo2` and `custom_code`) and `beaupi/MolmoWeb-8B-oQ8` (25 downloads). No 4-bit build and no 4B MLX build found. — [HF model search](https://huggingface.co/models?search=MolmoWeb), [ravilution/MolmoWeb-8B-8bit](https://huggingface.co/ravilution/MolmoWeb-8B-8bit), [MolmoWeb-4B card](https://huggingface.co/allenai/MolmoWeb-4B)
- Holo1 / 1.5 (Qwen2.5-VL base): GGUF from mradermacher, Mungert, DevQuasar; MLX `mlx-community/Holo1-{3B,7B}` at 3/4/6/8-bit and bf16, `mlx-community/holo1.5-7b-mlx`. — [HF model search](https://huggingface.co/models?search=Holo1)
- Holo2 (4B / 8B / 30B-A3B / 235B-A22B): GGUF with mmproj from mradermacher and Mungert; MLX only `mlx-community/Holo2-8B-bf16` (unquantised); EXL3 builds. — [HF model search](https://huggingface.co/models?search=Holo2)
- Holo3-35B-A3B: GGUF from mradermacher, mudler, DevQuasar; MLX `mlx-community/Holo3-35B-A3B-8bit`. — [HF model search](https://huggingface.co/models?search=Holo3)
- Holo3.1: first official GGUF, `Hcompany/Holo-3.1-35B-A3B-GGUF` (Q4_K_M 21.3 GB, BF16 69.4 GB, 61k downloads, Apache 2.0), plus official FP8 and NVFP4; community GGUF for 0.8B / 4B / 9B; MLX 4-bit and 8-bit for 4B / 9B / 35B-A3B from pipenetwork. Official quantised checkpoints are for the 35B-A3B only. — [Hcompany/Holo-3.1-35B-A3B-GGUF](https://huggingface.co/Hcompany/Holo-3.1-35B-A3B-GGUF), [Holo3.1 HF blog](https://huggingface.co/blog/Hcompany/holo31)
- Holo4: official `Hcompany/Holo4-27B-GGUF` and `Holo4-35B-A3B-GGUF` (Q4_K_M + mmproj), FP8, NVFP4; bartowski GGUF (40k downloads); community MLX. Holo4-35B-A3B is Apache 2.0; Holo4-27B is CC BY-NC 4.0. — [Hcompany/Holo4-27B](https://huggingface.co/Hcompany/Holo4-27B), [Holo4 announcement](https://hcompany.ai/newsroom/holo4)
- A user converting Holo-3.1-4B to MLX on release day hit `ValueError: Received 1 parameters not in model: language_model.lm_head.weight`; working MLX builds appeared two days later. — [HF discussion, Holo-3.1-4B #1](https://huggingface.co/Hcompany/Holo-3.1-4B/discussions/1), [pipenetwork/Holo-3.1-4B-MLX-4bit](https://huggingface.co/pipenetwork/Holo-3.1-4B-MLX-4bit)
- Ollama: no entry for any of the three in the official library. Community uploads exist for Fara-7B (`maternion/fara`) and Holo (`ahmadwaqar/holo-3.1`, `sparksammy/hcompany-holo2`, `lazarevtill/Holo1-7B`, `ollamaced/holo1_7B_q8_0`); none for MolmoWeb. H Company's card gives `ollama run hf.co/Hcompany/Holo-3.1-35B-A3B-GGUF:Q4_K_M`. — [Ollama search: holo](https://ollama.com/search?q=holo), [HF discussion, Fara-7B #10](https://huggingface.co/microsoft/Fara-7B/discussions/10), [Hcompany/Holo-3.1-35B-A3B-GGUF](https://huggingface.co/Hcompany/Holo-3.1-35B-A3B-GGUF)

**Weight file sizes (disk; add the vision projector, then context)**

GGUF sizes are Q4_K_M / Q8_0 plus the f16 mmproj; MLX sizes are whole-repo weights.

| Model | GGUF Q4_K_M | GGUF Q8_0 | mmproj f16 | MLX 4-bit | MLX 8-bit | Source |
|---|---|---|---|---|---|---|
| Fara-7B | 4.68 GB | 8.10 GB | 1.35 GB | 5.65 GB | 9.46 GB | [bartowski](https://huggingface.co/bartowski/microsoft_Fara-7B-GGUF/tree/main), [mlx-community](https://huggingface.co/mlx-community/Fara-7B-4bit/tree/main) |
| Fara1.5-4B | 2.88 GB | 4.49 GB | 0.67 GB | 4.22 GB (OptiQ) | 5.16 GB | [bartowski](https://huggingface.co/bartowski/Fara1.5-4B-GGUF/tree/main), [mlx-community](https://huggingface.co/mlx-community/Fara1.5-4B-8bit/tree/main) |
| Fara1.5-9B | 5.91 GB | 9.55 GB | 0.92 GB | 8.03 GB (OptiQ) | 10.45 GB | [bartowski](https://huggingface.co/bartowski/Fara1.5-9B-GGUF/tree/main), [mlx-community](https://huggingface.co/mlx-community/Fara1.5-9B-8bit/tree/main) |
| Fara1.5-27B | 17.53 GB | 28.67 GB | 0.93 GB | 21.28 GB (OptiQ) | none found | [bartowski](https://huggingface.co/bartowski/Fara1.5-27B-GGUF/tree/main), [mlx-community](https://huggingface.co/mlx-community/Fara1.5-27B-OptiQ-4bit/tree/main) |
| MolmoWeb-4B | none | none | n/a | none | none (full weights 19.4 GB) | [allenai](https://huggingface.co/allenai/MolmoWeb-4B/tree/main) |
| MolmoWeb-8B | none | none | n/a | none | 12.90 GB / 10.17 GB (full weights 34.7 GB) | [ravilution](https://huggingface.co/ravilution/MolmoWeb-8B-8bit/tree/main), [beaupi](https://huggingface.co/beaupi/MolmoWeb-8B-oQ8/tree/main) |
| Holo1-7B, Holo1.5-7B | 4.68 GB | 8.10 GB | 1.35 GB | 5.64 GB (Holo1) | 9.45 GB (Holo1) | [mradermacher](https://huggingface.co/mradermacher/Holo1.5-7B-GGUF/tree/main), [mlx-community](https://huggingface.co/mlx-community/Holo1-7B-4bit/tree/main) |
| Holo2-4B | 2.72 GB | 4.69 GB | 0.84 GB | none | none | [mradermacher](https://huggingface.co/mradermacher/Holo2-4B-GGUF/tree/main) |
| Holo2-8B | 5.03 GB | 8.71 GB | 1.16 GB | none (bf16 17.6 GB) | none | [mradermacher](https://huggingface.co/mradermacher/Holo2-8B-GGUF/tree/main) |
| Holo2-30B-A3B | 18.56 GB | 32.48 GB | 1.08 GB | none | none | [mradermacher](https://huggingface.co/mradermacher/Holo2-30B-A3B-GGUF/tree/main) |
| Holo3-35B-A3B | 21.17 GB | 36.90 GB | 0.90 GB | none found | 40.81 GB | [mradermacher](https://huggingface.co/mradermacher/Holo3-35B-A3B-GGUF/tree/main), [mlx-community](https://huggingface.co/mlx-community/Holo3-35B-A3B-8bit/tree/main) |
| Holo-3.1-4B | 3.07 GB | 5.16 GB | 0.67 GB | 3.99 GB | 6.10 GB | [mradermacher](https://huggingface.co/mradermacher/Holo-3.1-4B-GGUF/tree/main), [pipenetwork](https://huggingface.co/pipenetwork/Holo-3.1-4B-MLX-4bit/tree/main) |
| Holo-3.1-9B | 5.63 GB | 9.53 GB | 0.92 GB | 7.45 GB | 11.93 GB | [mradermacher](https://huggingface.co/mradermacher/Holo-3.1-9B-GGUF/tree/main), [pipenetwork](https://huggingface.co/pipenetwork/Holo-3.1-9B-MLX-4bit/tree/main) |
| Holo-3.1-35B-A3B | 21.30 GB (official) | n/a | 0.90 GB | 23.49 GB | 40.81 GB | [Hcompany](https://huggingface.co/Hcompany/Holo-3.1-35B-A3B-GGUF/tree/main), [pipenetwork](https://huggingface.co/pipenetwork/Holo-3.1-35B-A3B-MLX-4bit/tree/main) |
| Holo4-27B | 16.88 GB (official) | n/a | 0.93 GB | community only | community only | [Hcompany](https://huggingface.co/Hcompany/Holo4-27B-GGUF/tree/main) |
| Holo4-35B-A3B | 21.30 GB (official) | 36.91 GB | 0.90 GB | 21.10 GB (oQ4) | none found | [Hcompany](https://huggingface.co/Hcompany/Holo4-35B-A3B-GGUF/tree/main), [bartowski](https://huggingface.co/bartowski/Hcompany_Holo4-35B-A3B-GGUF/tree/main) |

**Vision-encoder support in the runtimes**

- llama.cpp's multimodal docs list Qwen2.5-VL (3B / 7B / 32B / 72B) among supported families; every Fara and Holo GGUF repo above ships an `mmproj` file, including the Qwen3.5-based Fara1.5 and Holo3.1 and the Holo4 builds. — [llama.cpp multimodal.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md), [bartowski/Fara1.5-9B-GGUF](https://huggingface.co/bartowski/Fara1.5-9B-GGUF/tree/main)
- mlx-vlm documents Qwen3.5 and Qwen3.8 usage; its model table lists MolmoPoint but no Molmo2 or MolmoWeb entry was found in the README. — [mlx-vlm README](https://github.com/Blaizzy/mlx-vlm)
- The OptiQ MLX builds of Fara1.5 keep the vision tower at bf16 and quantise the language model to mixed 4/8-bit (5.21 bits per weight for the 9B); the image path requires the `optiq` server, and stock `mlx-lm` loads the repo text-only. The bit allocation was copied from the Qwen3.5-9B build, not recomputed for Fara. — [mlx-community/Fara1.5-9B-OptiQ-4bit](https://huggingface.co/mlx-community/Fara1.5-9B-OptiQ-4bit)
- MolmoWeb, official backends: `native` (molmo/olmo checkpoint) and `hf` (Transformers) behind a FastAPI `/predict` server, or Modal. "We leave vLLM integration to users"; "vLLM does not support the exact attention backend used in OLMo, which may lead to unexpected behavior or reduced accuracy." No MLX, llama.cpp or Apple Silicon notes. — [allenai/molmoweb README](https://github.com/allenai/molmoweb)
- MolmoWeb's Transformers checkpoint did not match native inference at release (wrong chat template, image processing differences); Ai2 fixed it on 30 March 2026 after a community report. — [HF discussion, MolmoWeb-8B #2](https://huggingface.co/allenai/MolmoWeb-8B/discussions/2)

**Serving gotchas reported by users and vendors**

- Fara1.5 on llama-server: the model emits an opening `<think>` tag and never closes it, so with default reasoning extraction the whole output lands in `reasoning_content` and `content` is empty; Magentic-UI then shows `list index out of range. Retrying (1/3)...` on every task. Fix: start llama-server with `--reasoning-format none`. Microsoft staff acknowledged it (GitHub issue #82). — [HF discussion, Fara1.5-27B #4](https://huggingface.co/microsoft/Fara1.5-27B/discussions/4)
- Fara-7B on Ollama with an 8 GB laptop GPU: the server started but fara-cli "failed when making its first model call"; the reporter suspects Ollama's OpenAI-compatible endpoint and Qwen2.5-VL image input, or VRAM. Open since 22 Feb 2026 with no maintainer reply. — [microsoft/fara issue #58](https://github.com/microsoft/fara/issues/58)
- Fara settings: "context length is set to at least 15000 tokens and temperature to 0"; the agent keeps the last 3 screenshots; "The screen resolution Fara is most commonly trained with is 1440×900. Match this in your sandbox for the most reliable grounding." Microsoft has tested bf16 on A6000, A100, H100 and B200 only. — [microsoft/fara README](https://github.com/microsoft/fara), [Fara1.5-9B model card](https://huggingface.co/microsoft/Fara1.5-9B)
- Holo4 on llama.cpp, from H Company staff: temperature 0.8, top-p 0.95, top-k 20, min-p 0, repeat penalty 1.0, thinking enabled at medium effort, earlier reasoning kept in history, only the last 3 screenshots sent. "llama.cpp's own defaults differ (min_p 0.05, top_k 40), so set these explicitly." — [HF discussion, Holo4-35B-A3B-GGUF #3](https://huggingface.co/Hcompany/Holo4-35B-A3B-GGUF/discussions/3)
- Microsoft found that for Fara1.5 "enabling thinking at inference time for agentic web tasks adds substantial input tokens to the trajectory with minimal to no performance gains". — [Fara-1.5 paper](https://arxiv.org/html/2606.20785v2)

**Speed**

- The only step-time measurement found for any of the three: Holo3.1-35B-A3B on an NVIDIA DGX Spark, 6.8 s per step at FP8 falling to 3.3 s with NVFP4 plus harness optimisations (vendor and NVIDIA). NVFP4 token throughput is 1.41× FP8 and 1.74× BF16. The post says Apple Silicon reference numbers are included, but they are in a chart, not the text. — [Holo3.1 HF blog](https://huggingface.co/blog/Hcompany/holo31)
- A third-party headline claims "140ms Step Time" for Holo3.1 on 12 GB GPUs. Unverified, single secondary source, and at odds with H Company's own 3.3 s. — [ChatForest](https://chatforest.com/builders-log/holo-3-1-local-agent-12gb-gpu-builder-guide/)
- MolmoWeb: no latency figures; the paper says the model "is not optimized for latency" and that quantisation or pruning could help. — [MolmoWeb paper](https://arxiv.org/html/2604.08516)
- Fara1.5: no latency, steps-per-task or cost figures in the blog, card or README; the paper says "the larger and more accurate models tend to take less steps". — [Fara-1.5 paper](https://arxiv.org/html/2606.20785v2)
- Hardware anecdotes: Fara-7B GGUF "run on rtx 5060ti 16 gb vram"; an LM Studio user on macOS reports the Fara-7B Q4_K_S as a 5.8 GB download and Q8 as 9.5 GB. No tokens-per-second given. — [HF discussion, Fara-7B #6](https://huggingface.co/microsoft/Fara-7B/discussions/6), [HN thread 46061208](https://news.ycombinator.com/item?id=46061208)

**Quantisation and grounding accuracy**

- H Company: FP8 and NVFP4 (W4A16) of Holo3.1-35B-A3B are about 2 points below BF16 on OSWorld; no figure is given for the Q4 GGUF. — [Holo3.1 HF blog](https://huggingface.co/blog/Hcompany/holo31); a secondary write-up says FP8 matches BF16 and only NVFP4 loses ~2 points — [dev.to](https://dev.to/monuminu/computer-use-agents-go-local-a-deep-technical-dive-into-on-device-gui-automation-quantized-2m3g)
- Nearest analogue measurement (a different GUI model, UI-Venus-2-9B, MLX): four 4-bit variants scored 56–60% on a 50-sample ScreenSpot-Pro subset with the vision tower left unquantised; the author puts the standard error at about ±7 points, so no loss is detectable at that sample size. Unverified, single model card. — [lethargicgeek/UI-Venus-2-9B-mlx-4bit](https://huggingface.co/lethargicgeek/UI-Venus-2-9B-mlx-4bit)
- The OptiQ Fara1.5 cards report no accuracy or grounding evaluation against full precision. — [mlx-community/Fara1.5-9B-OptiQ-4bit](https://huggingface.co/mlx-community/Fara1.5-9B-OptiQ-4bit)

### Inferences
- Approximate resident memory = weights + projector + roughly 1.5–3 GB for a 15k–32k context holding three screenshots. On that basis, at 4-bit: Fara1.5-4B and Holo-3.1-4B ≈ 5–6 GB; Fara-7B, Fara1.5-9B, Holo-3.1-9B ≈ 8–10 GB; Fara1.5-27B and Holo4-27B ≈ 20–22 GB; Holo 35B-A3B ≈ 24–26 GB. At 8-bit: 4B ≈ 7–8 GB; 9B ≈ 12–13 GB; 27B ≈ 32 GB; 35B-A3B ≈ 40–43 GB. These are estimates from file sizes, not measurements.
- A 24 GB GPU holds any 4B / 7B / 9B model at 8-bit, and Fara1.5-27B or Holo4-27B at Q4 with little headroom; the 35B-A3B Q4 (21.3 GB + 0.9 GB projector) is marginal on 24 GB once context is added. A 32 GB Mac runs the 27B class at 4-bit; 48–64 GB runs everything listed at 4-bit and the 9B class at bf16.
- The 35B-A3B Holo models activate about 3B parameters per token, so they should generate at roughly small-model speed while needing large-model memory. That suits unified-memory Macs better than 24 GB GPUs. Not measured here.
- MolmoWeb on a Mac today means Transformers on MPS at full precision (≈19 GB for 4B, ≈35 GB for 8B as stored) or an untested community 8-bit MLX build that needs custom code. It is the least practical of the three to run locally.
- Keeping the vision tower at full precision (OptiQ, and the f16 mmproj in GGUF builds) is the common practice, so the plausible grounding risk from 4-bit sits in the language model's coordinate output, which nobody has measured for these models.

### Gaps
- No tokens-per-second or seconds-per-step measurement on Apple Silicon was found for any Fara, MolmoWeb or Holo model. No single-24 GB-GPU measurement either (the DGX Spark figure is the only one).
- No measurement of ScreenSpot or task success at Q4 / Q8 vs bf16 for any of the three families. H Company's "~2 points on OSWorld" for FP8 / NVFP4 is the only vendor datum, and the secondary source contradicts it on FP8.
- LM Studio's catalogue was not checked directly; LM Studio support is inferred from the GGUF and MLX builds and from Microsoft's README.
- A search summary claimed Ollama's Apple Silicon backend moved to MLX "since v0.19"; this was not verified against Ollama's release notes.
- A search summary of H Company's docs said the larger Holo3 122B model is API-only; the page fetched did not show that text. Unverified.

## 4. Harness support, and which harnesses can attach to an existing Chrome profile

### Takeaway
Each family works out of the box only in its vendor's harness, and none of those harnesses documents attaching to a user's running Chrome. The general frameworks that do attach to a real Chrome (browser-use, Playwright MCP, Chrome DevTools MCP, Nanobrowser) expect a tool-calling or code-writing general model, not a pixel-action specialist, so pairing them with Fara, MolmoWeb or Holo means writing an adapter.

### Cited Findings

**Vendor harnesses**

- Fara: `fara-cli` (Playwright; `--headful` shows the browser; takes any OpenAI-compatible `--base_url`). The model card says "Please use only with the harness developped in" Fara CLI or Magentic-Lite. CDP attach and user profiles are not covered. — [microsoft/fara README](https://github.com/microsoft/fara), [Fara1.5-9B model card](https://huggingface.co/microsoft/Fara1.5-9B)
- MagenticLite is "the next generation of Magentic-UI", built around Fara plus a MagenticBrain orchestrator; "Browser sessions run inside a lightweight VM sandbox (Quicksand)"; quick start is for "macOS or Windows (WSL)". A sandboxed VM browser is by design not the user's Chrome. — [microsoft/magentic-ui](https://github.com/microsoft/magentic-ui)
- Microsoft's safety note: "Don't run this model with unrestricted browser access on a machine that has anything sensitive on it." — [Fara1.5-9B model card](https://huggingface.co/microsoft/Fara1.5-9B)
- A community harness for Fara-7B GGUF exists (`pmbstyle/fara-agent`). Not examined. — [HF discussion, Fara-7B #6](https://huggingface.co/microsoft/Fara-7B/discussions/6)
- MolmoWeb: only its own repo's client. Browser environments: `simple` (local Chromium via Playwright), Browserbase, and Browser Use Cloud. CDP attach is not mentioned. The eval harness also drives `gemini_cua`, `gemini_axtree` and `gpt_axtree` agents. — [allenai/molmoweb README](https://github.com/allenai/molmoweb)
- Holo, old path: Surfer-H CLI supported Holo1 and Holo1.5 with local vLLM, but "has been deprecated and is no longer maintained" and was archived on 25 June 2026. — [hcompai/surfer-h-cli](https://github.com/hcompai/surfer-h-cli)
- Holo, current path: the `hai-agents` SDK and `holo` CLI. `holo --local` runs the agent loop on the user's machine, but "model calls still go to H unless you run your own model server"; pointing `HAI_AGENT_RUNTIME_BASE_URL` at a local server keeps inference local while "only the agent lookup goes to H". Sign-in (`holo login`) is still required. `h/holo-desktop` "uses your mouse and keyboard". — [H Company docs](https://hub.hcompany.ai/holo-desktop-cli/getting-started/hosted-or-local-models), [hai-agents README](https://github.com/hcompai/hai-agents-python)
- Holo in the user's own Chrome: HoloTab is a Chrome extension "powered by Holo3", using H's hosted model. hai-agents also offers cloud "browser profiles" that restore saved cookies. — [HN thread on HoloTab](https://news.ycombinator.com/item?id=47776595), [hai-agents README](https://github.com/hcompai/hai-agents-python)

**Third-party frameworks**

- Cua's agent SDK listed Fara-7B as a browser-tool model (`azure_ml/Fara-7B`) and Holo1.5 as a grounding-only model to be composed with a planner (`huggingface-local/Hcompany/Holo1.5-{3B,7B,72B}`); no MolmoWeb support was found. — [Cua docs: browser tool](https://cua.ai/docs/cua/guide/fundamentals/browser-tool), [Cua docs: composed agents](https://cua.ai/agent-sdk/supported-agents/composed-agents) (from search summaries, pages not opened; unverified). The `cua-agent` package is now listed under "Deprecated packages". — [trycua/cua README](https://github.com/trycua/cua)
- browser-use 1.0: the model "does it in a real browser by writing Python" against raw CDP. `Browser('chrome')` is "the Chrome you have open, with your logins (turn on chrome://inspect/#remote-debugging once)"; `Browser('chrome', profile='Work')` uses a temporary copy of a profile; any OpenAI-compatible server works via `ChatOpenAI(model, base_url=...)`. No Fara, Holo or MolmoWeb integration is mentioned. — [browser-use README](https://github.com/browser-use/browser-use)
- Playwright MCP: `--extension` connects "to a running browser instance (Edge/Chrome only)" through the Playwright Extension, to "leverage your logged-in sessions"; `--cdp-endpoint` and `--user-data-dir` are also available. It is a tool server for a tool-calling model. — [microsoft/playwright-mcp README](https://github.com/microsoft/playwright-mcp)
- Chrome DevTools MCP supports "connecting to a running Chrome instance instead of starting a new one". — [chrome-devtools-mcp README](https://github.com/ChromeDevTools/chrome-devtools-mcp)
- Nanobrowser is a Chrome extension that drives the user's own browser through `chrome.debugger`; local models via Ollama, LM Studio, llama.cpp or vLLM; "A model must support tool calling"; "Local models work best for simple, clear tasks. We currently recommend Qwen3.8 27B." — [nanobrowser README](https://github.com/nanobrowser/nanobrowser)
- Stagehand launches a local Chrome with a persistent `userDataDir`; its examples use hosted general models. — [stagehand README](https://github.com/browserbase/stagehand)
- UI-TARS Desktop is "driven by UI-TARS and Seed-1.5-VL/1.6 series models", with local and remote computer and browser operators. No Fara, Holo or MolmoWeb support is documented. — [UI-TARS-desktop README](https://github.com/bytedance/UI-TARS-desktop)

**Chrome's own constraint on attaching to a real profile**

- From Chrome 136, `--remote-debugging-port` and `--remote-debugging-pipe` "will no longer be respected if attempting to debug the default Chrome data directory"; they "must now be accompanied by the `--user-data-dir` switch to point to a non-standard directory". — [Chrome for Developers blog, 17 March 2025](https://developer.chrome.com/blog/remote-debugging-port)

### Inferences
- Three routes now reach a user's real, logged-in Chrome: the in-browser opt-in at `chrome://inspect/#remote-debugging` (browser-use, Chrome DevTools MCP), an extension bridge (Playwright MCP `--extension`, Nanobrowser, HoloTab), or a copied / dedicated profile directory. The old "launch your default profile with a debugging port" route is closed.
- Fara, MolmoWeb and Holo each emit their own action schema with pixel coordinates from a screenshot of fixed size. To drive an existing Chrome with one of them, the shortest path is to keep the vendor's prompt and parser and swap only the browser backend: point Playwright at a CDP endpoint (`connect_over_cdp`) or the Playwright extension in place of the launch call in `fara-cli` or MolmoWeb's `simple` environment. Neither repo documents this; it is a small code change, not a setting.
- Viewport mismatch is a real risk when attaching to a user's window: Fara expects about 1440×900, and a differently sized live window shifts the coordinate distribution the model was trained on.
- For "local model + my real Chrome, today, without writing code", the working combination is a general tool-calling model (Nanobrowser's own recommendation is Qwen3.8 27B) in Nanobrowser, browser-use or Playwright MCP, not any of the three specialist families. Holo4-35B-A3B, as a general Qwen3.6 fine-tune with tool calling, is the one specialist that might slot into those harnesses unchanged; untested.

### Gaps
- No documented example was found of Fara, MolmoWeb or Holo attached over CDP or an extension to a user's existing Chrome profile.
- Whether MagenticLite's Quicksand sandbox can be bypassed for a host browser was not checked (its Configuration docs were not read).
- Cua's current (post-deprecation) support for these models was not confirmed.
- Whether HoloTab can be pointed at a self-hosted Holo endpoint was not determined.

## 5. Real-world user reports comparing them

### Takeaway
Almost none exist. No hands-on write-up was found that runs two of the three families side by side, and there is no visible community preference. What exists is a handful of single-model reports: Fara1.5 draws the most positive local-use comments, Holo3's vendor numbers proved hard to reproduce without the vendor's loop, and MolmoWeb has close to no community traffic.

### Cited Findings

- Community interest by proxy (Hugging Face downloads and likes, 12 Nov 2026): Hcompany/Holo-3.1-35B-A3B-GGUF 61k downloads; bartowski Holo4-35B-A3B GGUF 40k; Holo2-4B 23k; bartowski Fara1.5 GGUFs 6–10k each; microsoft/Fara-7B 3.2k downloads and 624 likes; allenai/MolmoWeb-4B 1.7k and MolmoWeb-8B 0.8k; MolmoWeb MLX builds 25–33. — [HF model search](https://huggingface.co/models?search=Holo), [HF model search](https://huggingface.co/models?search=MolmoWeb)
- Hacker News: Fara-7B's launch thread drew 191 points and 85 comments; MolmoWeb's three submissions drew 9, 3 and 2 points with one comment in total; Holo3's and Holo4's announcements drew 1–4 points and no comments; Fara1.5-27B drew 3 points. — [HN 46061208](https://news.ycombinator.com/item?id=46061208), [HN 47721361](https://news.ycombinator.com/item?id=47721361), [HN 49077894](https://news.ycombinator.com/item?id=49077894)
- The Fara-7B HN thread is mostly about VRAM, synthetic data and use cases, not results. One commenter: "I can't imagine having an AI agent book anything or purchase anything... It should do the research and take me to the place where I need to take over." — [HN 46061208](https://news.ycombinator.com/item?id=46061208)
- Fara1.5, local use: "great work on Fara1.5, it's been really impressive to run locally" (27B on llama.cpp, after fixing the reasoning-format issue); "In my testing the 9B model appears to behave very well." — [HF discussion, Fara1.5-27B #4](https://huggingface.co/microsoft/Fara1.5-27B/discussions/4), [HF discussion, Fara1.5-9B #3](https://huggingface.co/microsoft/Fara1.5-9B/discussions/3)
- A developer building a Chrome-extension agent on a local Qwen3.5-122B looked at Fara1.5-27B and reported "Nope, not what I thought it was after all", without saying why. — [HN 49077894](https://news.ycombinator.com/item?id=49077894)
- Fara-7B failure reports are about serving, not behaviour: Ollama on 8 GB failing on the first model call; llama-server returning empty content. — [microsoft/fara issue #58](https://github.com/microsoft/fara/issues/58), [HF discussion, Fara1.5-27B #4](https://huggingface.co/microsoft/Fara1.5-27B/discussions/4)
- Holo3: a self-hosted run reached 23% on OSWorld with a simple loop; H Company's answer was to use its cookbook loop. — [HF discussion, Holo3-35B-A3B #5](https://huggingface.co/Hcompany/Holo3-35B-A3B/discussions/5)
- HoloTab (hosted Holo3 in a Chrome extension): seven short HN comments, e.g. "Tried and seems to work good enough at least for the stuff I tried, which is mostly googeling and summarizing"; one sceptic asks "Does it actually work? Benchmarks are one thing". The positive comments are brief and carry no task detail. — [HN 47776595](https://news.ycombinator.com/item?id=47776595)
- MolmoWeb: the only substantive community thread is a bug report that Transformers inference did not match native inference. — [HF discussion, MolmoWeb-8B #2](https://huggingface.co/allenai/MolmoWeb-8B/discussions/2)
- Vendor-stated failure modes for Fara1.5: misled by "deceptive or low-quality page rendering" and prompt injection in page content; "a misclick early in a sequence can compound"; English-only training. — [Fara1.5-9B model card](https://huggingface.co/microsoft/Fara1.5-9B)
- Several "local deployment guides" for Holo3.1 report no runs of their own. One hardware-tier guide gives recommendations with no measurements; another repeats vendor figures and flags its own statistics as needing verification. — [knightli.com](https://knightli.com/en/2026/06/12/holo-3-1-local-agent-openclaw-llamacpp/), [dev.to](https://dev.to/monuminu/computer-use-agents-go-local-a-deep-technical-dive-into-on-device-gui-automation-quantized-2m3g)

### Inferences
- Download counts say local users are mostly pulling Holo (3.1 and 4, especially the 35B-A3B GGUFs) and Fara1.5 GGUFs; MolmoWeb has almost no local user base. Downloads measure curiosity and packaging convenience, not preference after use, and many Holo 35B downloads are likely for general agent or coding use of a Qwen fine-tune rather than browser control.
- The reports that do exist point at the same lesson as the benchmarks: results depend on the loop around the model (prompt format, screenshot history, sampling, reasoning parsing) more than on the weights. Fara's and Holo's worst user-reported failures were harness and serving mismatches.
- Much of the searchable "review" content for these models is unsourced or machine-written repetition of vendor claims; it should not be counted as user evidence.

### Gaps
- No Reddit r/LocalLLaMA thread was surfaced by four differently worded searches. Reddit was not searched directly, so threads may exist; none can be cited.
- No report was found of multi-step reliability, loop or repetition failures, or speed from someone running Fara1.5, MolmoWeb or Holo3 / 3.1 / 4 on a Mac.
- No user comparison of any two of the three families was found. "Which one people prefer and why" cannot be answered from evidence.

## 6. Where do these sub-32B open models stand against closed frontier browser agents (for scale)?

### Takeaway
On the stricter web benchmark the best open sub-32B figure (Fara1.5-27B, 72.3%, vendor-run, WebJudge) sits about 10–20 points below current frontier agents and above the 2025 generation of closed computer-use models. On desktop benchmarks H Company reports Holo4-27B within a point of the frontier on the original OSWorld but about 20 points behind on OSWorld 2.0.

### Cited Findings

- Online-Mind2Web, frontier rows (mixed judges, mostly self-reported): Browser Use Cloud 97.0% (custom judge); GPT-5.4 native computer use 93.0% (OpenAI, raw data not public); ABP + Claude Opus 4.6 90.53% (all 300 results public); CUAWright + GPT-5.5 89.4%; Yutori Navigator 78.7% human / 64.7% WebJudge; Gemini 2.5 CU 69.0% human / 57.3% WebJudge; OpenAI Operator 61.3% human. — [Steel Online-Mind2Web](https://leaderboard.steel.dev/leaderboards/online-mind2web.md)
- Open sub-32B on the same benchmark (all vendor-run, WebJudge o4-mini): Fara1.5-27B 72.3, Fara1.5-9B 63.4, Fara1.5-4B 57.3, MolmoWeb-8B 35.3, Fara-7B 34.1, MolmoWeb-4B 31.3. Holo: no figure. — [microsoft/fara README](https://github.com/microsoft/fara), [MolmoWeb paper](https://arxiv.org/html/2604.08516)
- Like-for-like inside Microsoft's harness and judge: the GPT-5.4-based teacher scores 83.4% on Online-Mind2Web and 93.4% on WebVoyager against Fara1.5-27B's 72.3% and 89.3%; GPT-5 SoM scores 57.7% and 90.6%. — [microsoft/fara README](https://github.com/microsoft/fara)
- Like-for-like inside Alibaba's harness (pass@1, 100 steps): GPT-5.5 74.7% and GPT-5 67.1% on Online-Mind2Web; the 27B open Wuying agent 66.7%. — [Wuying paper](https://arxiv.org/html/2608.17319v1)
- WebVoyager: frontier systems 97–99% (self-reported); Fara1.5-27B 89.3, Fara1.5-9B 86.6, Holo2-30B-A3B 83.0, Holo2-8B 80.2, MolmoWeb-8B 78.2 (each vendor's own run). — [Steel full dump](https://leaderboard.steel.dev/llms-full.txt), [microsoft/fara README](https://github.com/microsoft/fara)
- OSWorld (H Company's table; frontier rows are public figures from other harnesses): Holo4-27B 85.2% at $0.08 per task, Holo4-35B-A3B 80.8%, against Fable 5 86.0%, Qwen3.8 Max 86.1%, GPT-5.5 78.7%. OSWorld 2.0: Holo4-27B 61.7% and Holo4-35B-A3B 30.9% against Opus 5.5 81.8% and GPT-6 Astra 73.5%. — [Holo4 announcement](https://hcompany.ai/newsroom/holo4)

### Inferences
- The fair scale statement is the same-harness one: in Microsoft's own setup a frontier model beats the best open 27B by about 11 points on Online-Mind2Web and 4 on WebVoyager. Cross-source gaps (72 vs 93–97) mix judges and should not be quoted as the gap.
- The open-closed gap widens with task length: near zero on saturated WebVoyager and the original OSWorld, about 10 points on Online-Mind2Web, about 20 or more on OSWorld 2.0.
- The 4B–9B class that fits comfortably on a laptop sits at 57–63% on Online-Mind2Web by its vendor's count, roughly where closed computer-use models were in 2025.

### Gaps
- No frontier model and open model have been scored by a neutral party on Online-Mind2Web under human evaluation in 2026.
- No Holo figure exists on any web-only benchmark later than Holo2's vendor WebVoyager numbers, so Holo cannot be placed on the web scale.
