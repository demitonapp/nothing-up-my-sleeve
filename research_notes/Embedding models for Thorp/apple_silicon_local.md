# Running text embedding models locally on Apple Silicon (as of 12 Nov 2026)

Scope: which current embedding models run well on an M-series Mac, through what tooling, at what speed and memory, with what quantisation; precision pitfalls; and a rough time and cost estimate for embedding ~1B tokens on a Mac versus a rented RTX 4090 or H100. Written for Thorp, which trains small LMs with MLX on the same Mac, so the embedding job must not take over the GPU.

Overall caveat: published Apple Silicon *embedding* throughput figures are scarce and mostly anecdotal. Most "tokens/s on M4" figures online are decode (generation) speeds, which say nothing about encoder throughput. Treat every Mac figure below as an order of magnitude only, and plan a 10-minute local benchmark before committing.

## Which models have which local tooling (MLX, GGUF/llama.cpp, Ollama, LM Studio, sentence-transformers/MPS)

### Takeaway
Qwen3-Embedding (0.6B/4B/8B), the Jina v5 text models and EmbeddingGemma 2 have the broadest local support: MLX, GGUF/llama.cpp, Ollama, and sentence-transformers. The reference MLX library, Blaizzy/mlx-embeddings, does *not* list a Gemma architecture. EmbeddingGemma on MLX therefore comes through mlx-community conversions or Google's own MLX listing rather than that library's documented architecture list. For a 300M-class and a 600M-class candidate, EmbeddingGemma (300M v1, or the 270M text tower of v2) and Qwen3-Embedding-0.6B are the natural pair.

### Cited Findings
**mlx-embeddings (Blaizzy)**
- The supported architectures listed on the GitHub page are XLM-RoBERTa, BERT, ModernBERT, Qwen3, Qwen3-VL, Llama Bidirectional, Llama Nemotron VL and OpenAI Privacy Filter. Gemma/EmbeddingGemma is not mentioned. — [GitHub Blaizzy/mlx-embeddings](https://github.com/Blaizzy/mlx-embeddings)
- XLM-RoBERTa support implies BGE-M3, which is XLM-R based. That inference is mine; the repo does not name BGE-M3. — [GitHub Blaizzy/mlx-embeddings](https://github.com/Blaizzy/mlx-embeddings)
- The converter has a `--quantize` option with modes `affine` (default, 4-bit, group 64), `mxfp4` (group 32), `nvfp4` (group 16) and `mxfp8` (8-bit, group 32). `--q-bits` and `--q-group-size` override them. `--dtype` defaults to **float16**, with bfloat16 and float32 as options. That default matters for Gemma; see the precision section. — [GitHub Blaizzy/mlx-embeddings](https://github.com/Blaizzy/mlx-embeddings)
- The library supports single and batch processing (`batch_encode_plus` with padding/truncation, example max_length 512). The page gives no release dates and no speed figures. — [GitHub Blaizzy/mlx-embeddings](https://github.com/Blaizzy/mlx-embeddings)
- The Swift port mzbac/mlx.embeddings lists Qwen3 and uses `mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ` as an example. — [GitHub mzbac/mlx.embeddings](https://github.com/mzbac/mlx.embeddings) (via search snippet)

**EmbeddingGemma (v1, 300M) and EmbeddingGemma 2**
- There is an MLX 4-bit conversion, `mlx-community/embeddinggemma-300m-4bit`, converted from `google/embeddinggemma-300m-qat-q4_0-unquantized`. It is gated behind the Gemma licence and loaded with `mlx_embeddings.load(...)`. — [HF mirror of the mlx-community README](https://hg.istephan-squireso.workers.dev/mlx-community/embeddinggemma-300m-4bit/blob/main/README.md). This is a mirror, not the live HF page, so the download count and date are unverified.
- An aggregator lists a 6-bit MLX variant, `mlx-community/embeddinggemma-300m-6bit`. — [Mixpeek](https://mixpeek.com/model/mlx-community/embeddinggemma-300m-6bit)
- Unsloth publishes a GGUF build of embeddinggemma-300m. — [HF unsloth/embeddinggemma-300m-GGUF](https://huggingface.co/unsloth/embeddinggemma-300m-GGUF)
- Ollama's embeddings documentation uses `embeddinggemma` and `qwen3-embedding` as its examples. — [Ollama docs: embeddings](https://docs.ollama.com/capabilities/embeddings.md)
- Google announced EmbeddingGemma 2 on **6 Oct 2026**. It is built on Gemma 4 and licensed Apache 2.0, which removes the Gemma licence gate. It has 740M parameters in total, but text-only use needs about 270M; the vision encoder adds 170M and the audio encoder 300M. Context is 8K and the output is 768-d. Google lists serving support for transformers, sentence-transformers, **MLX**, vLLM, **llama.cpp** (a GGUF build), SGLang, **Ollama** and **LM Studio**. — [Google blog: EmbeddingGemma 2](https://blog.google/innovation-and-ai/technology/developers-tools/embeddinggemma-2?authuser=2)
- The v2 model card breaks the 270M text model into a 130M backbone and a 140M embedder. Footprints: text-only 270M, text+image 440M, text+audio 570M. MTEB multilingual v2 is 61.36 (v1: 61.15), MTEB code is 78.68 (v1: 68.76), and MTEB English v2 is 68.46. — [EmbeddingGemma 2 model card](https://ai.google.dev/gemma/docs/embeddinggemma/model_card_2?hl=pt-br)
- I found no official Ollama tag page for `embeddinggemma-2`; a search summary flagged the tag as unverified. — [Ollama docs](https://docs.ollama.com/capabilities/embeddings.md)

**Qwen3-Embedding (0.6B / 4B / 8B)**
- 0.6B model: 28 layers, 32K context, output dimension up to 1024, with MRL output dimensions from 32 to 1024. It uses last-token pooling with left padding. It is instruction-aware: queries need a one-line task instruction, documents need none, and omitting the instruction costs about 1–5% retrieval. MTEB English v2 is 70.70, Multilingual 64.33. Weights are stored in BF16, and the card's examples use float16 together with flash_attention_2. The card lists 283 quantised derivatives. — [HF Qwen/Qwen3-Embedding-0.6B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)
- Ollama hosts official `qwen3-embedding` builds with 0.6b, 4b and 8b tags. — [glukhov.org guide](https://glukhov.org/rag/embeddings/qwen3-embedding-qwen3-reranker-on-ollama/); [Ollama docs](https://docs.ollama.com/capabilities/embeddings.md)
- There is a community MLX server, jakedahn/qwen3-embeddings-mlx, that uses 4-bit DWQ checkpoints such as `Qwen3-Embedding-4B-4bit-DWQ`. — [GitHub jakedahn/qwen3-embeddings-mlx](https://github.com/jakedahn/qwen3-embeddings-mlx)

**Jina v5**
- jina-embeddings-v5-text-small and -nano launched around 18 Feb 2026 with official GGUF builds (14 quant levels from F16 down to IQ1_S, runnable via `llama-server` embedding mode) and official MLX builds (full precision, 4-bit and 8-bit, one repo per task adapter, e.g. `jinaai/jina-embeddings-v5-text-small-retrieval-mlx`). The licence is **CC-BY-NC-4.0**. — [Jina v5 launch post](https://jina.ai/news/jina-embeddings-v5-text-distilling-4b-quality-into-sub-1b-multilingual-embeddings); [HF jina-embeddings-v5-text-nano](https://huggingface.co/jinaai/jina-embeddings-v5-text-nano)
- The omni-nano model (7 May 2026) lists GGUF and MLX quantisations. — [Jina omni-nano page](https://jina.ai/models/jina-embeddings-v5-omni-nano/)
- Jina v4 GGUF: Jina's own article (Aug 2025) needed a patched `llama-embedding` build for efficient bulk embedding of a decoder-only embedder. It requires `--pooling mean`, and its `-ub < -b` mean-pooling fix is correct only for causal models. The vision tower was dropped, and Matryoshka truncation works only at the trained dims (128/256/512/1024/2048). — [Jina: Optimizing GGUFs for decoder-only embedding models](https://jina.ai/news/optimizing-ggufs-for-decoder-only-embedding-models)

**Granite, BGE-M3 and others**
- IBM Granite Embedding models range from 30M to 278M parameters. The 278M multilingual model is 768-d with a 512-token limit, and it is available in Ollama. — [morphllm Ollama embedding models](https://www.morphllm.com/ollama-embedding-models) (secondary source)
- Newer Granite R2 models (granite-97m-r2, granite-311m-r2) were benchmarked on Apple MPS in the Bekko paper; see the speed section. — [Bekko paper, arXiv 2607.25180](https://arxiv.org/html/2607.25180v1)
- BGE-M3 has 568M parameters, is 1024-d and takes up to 8192 tokens of input. — [Bekko paper, arXiv 2607.25180](https://arxiv.org/html/2607.25180v1)

### Inferences
- For Thorp, the most practical MLX-native path is `mlx-embeddings` with Qwen3-Embedding-0.6B (Qwen3 architecture, listed) or BGE-M3 (XLM-R, listed). EmbeddingGemma on MLX depends on community conversions, and I could not confirm the architecture in mlx-embeddings' documented list. Run it before relying on it.
- Ollama and LM Studio are convenient but add an HTTP server and their own GPU scheduling. For a batch job over tens of thousands of books, a direct Python loop (MLX, or sentence-transformers on MPS) gives more control over batch size and throttling.
- EmbeddingGemma 2's Apache 2.0 licence and 270M text-only tower make it the cleanest "300M-class" choice for licensing. Jina v5 is CC-BY-NC, which may matter if Thorp's outputs are ever commercial.

### Gaps
- I could not confirm whether mlx-embeddings has added Gemma or EmbeddingGemma 2 since the README was fetched. The README has no release history.
- Snowflake Arctic Embed 2, Nomic Embed v2 (MoE) and mxbai: not researched within the tool budget. GGUF builds of these are widely reported, but I have no citation for their MLX/Ollama status as of Nov 2026.
- I found no official `embeddinggemma-2` Ollama tag page or official GGUF repo URL; Google's blog only says a GGUF build exists.

## Published throughput on M-series chips, and memory at bf16 / 8-bit / 4-bit

### Takeaway
There is almost no rigorous public embedding benchmark on Apple Silicon. The best primary figure is from the Bekko paper (PyTorch MPS, M4 Max, batch 64, max 512 tokens): mE5-large (~560M) runs at **67 docs/s** and BGE-M3 at **~78 docs/s**, with granite-311m-r2 at 106 docs/s. The one MLX figure, 44K tok/s for 4-bit Qwen3-Embedding-0.6B on an M2 Max, is an unverified README claim. Memory is small: a 0.6B model at 4-bit is under 1 GB.

### Cited Findings
- **Bekko paper, Section 7.2, Apple M4 Max (macOS 26.5), PyTorch MPS, batch 64, max length 512, Natural Questions documents (docs/s):** bekko-a8m 592; mE5-small 370; bekko-a25m 351; granite-97m-r2 286; granite-311m-r2 106; mE5-large 67. BGE-M3 is about 78 docs/s (given outside the table). EmbeddingGemma-300m has only a CUDA figure, 1,678 docs/s, and no MPS figure. No MLX or CoreML results are reported. — [Bekko paper, arXiv 2607.25180](https://arxiv.org/html/2607.25180v1)
- **jakedahn/qwen3-embeddings-mlx, 16" MacBook Pro M2 Max 32 GB, 4-bit (DWQ), batch 32:** 0.6B ~44K tok/s, 4B ~18K tok/s, 8B ~11K tok/s. Memory is about 900 MB (0.6B), 2.5 GB (4B) and 4.5 GB (8B). The repo does not state sequence length or methodology and has few stars, so treat these as a headline claim. — [GitHub jakedahn/qwen3-embeddings-mlx](https://github.com/jakedahn/qwen3-embeddings-mlx)
- **E5-large-v2, M4 Max, batch 64:** ~3,120 tok/s. The methodology is loosely described, so this is anecdotal. — [Medium: optimized text embeddings](https://medium.com/@guyycodes/optimized-text-embeddings-performance-practical-applications-4812059a384c)
- **llama.cpp + Metal, M4 Max, all-MiniLM-L6-v2 (22M), short texts:** ~9.7K embeddings/s via the llama-cpp-2 Rust bindings. — [rust-embedding-bench (mirror)](https://github.2858349172.workers.dev/jerrythomas/rust-embedding-bench) (via search summary)
- **Jina v4 GGUF (3.09B), NVIDIA L4, not Apple:** about 3,400–4,100 tok/s with flash attention (best: IQ3_S, `-ub 512`, 4,143 tok/s). Flash attention gives about a 77% speed-up. Peak VRAM: F16 9.70 GB, Q8_0 6.36 GB, IQ3_M 4.69 GB, IQ1_S 4.04 GB. — [Jina GGUF article](https://jina.ai/news/optimizing-ggufs-for-decoder-only-embedding-models)
- **EmbeddingGemma 2 memory:** quantised, about 191 MB active RAM for the text-only weights and about 567 MB for full multimodal, measured on a Pixel 11 Pro. bf16 halves memory relative to fp32. — [Google blog](https://blog.google/innovation-and-ai/technology/developers-tools/embeddinggemma-2?authuser=2); [model card](https://ai.google.dev/gemma/docs/embeddinggemma/model_card_2?hl=pt-br)
- **EmbeddingGemma v1 in Ollama:** about a 307 MB download, with about 3.1 GB of memory cited by one guide (secondary source). — [search summary of Ollama guides](https://www.morphllm.com/ollama-embedding-models)
- Search pages such as willitrunai.com quote "~8 tok/s" for BGE-M3 on M4. That is a *decode* estimate and not meaningful for embeddings. — [willitrunai bge-m3 on M4](https://willitrunai.com/can-run/bge-m3-on-m4-mini-32gb)

### Inferences
- Rule-of-thumb weight memory (my arithmetic, not a citation) is parameters × bytes per parameter:
  - 300M model: ~0.6 GB at bf16, ~0.3 GB at 8-bit, ~0.15–0.2 GB at 4-bit.
  - 600M model: ~1.2 GB, ~0.6 GB and ~0.35 GB respectively.
  - Activations at batch 64 × 512 tokens add a few hundred MB.
  - Memory is not the constraint on any M-series Mac; GPU compute time shared with training is.
- The MPS and MLX anchors disagree by roughly 3–10×. The tokens per NQ document are unknown (often under 200, truncated at 512). At about 150 tokens per document, BGE-M3's 78 docs/s is only about 12K tok/s, versus the claimed 44K tok/s for 4-bit Qwen3-0.6B in MLX. Some of the gap is plausibly MLX plus 4-bit versus PyTorch MPS at fp16/fp32, and M2 Max versus M4 Max should go the other way. Neither figure is reliable enough to plan on without a local test.
- 4-bit weight quantisation speeds up memory-bound decoding, but an encoder forward pass at large batch is mostly compute-bound. On Apple GPUs, 4-bit may therefore cut memory much more than it raises throughput. This is inference from general principles; I found no Apple-specific encoder benchmark that isolates it.

### Gaps
- No published M1/M3/M5 embedding throughput for EmbeddingGemma, Qwen3-Embedding, Jina v5 or Granite with stated sequence lengths.
- No measured MLX-versus-MPS comparison for the same embedding model on the same chip.
- No Apple-specific measurement of 4-bit versus 8-bit versus bf16 encoder throughput.

## Precision pitfalls, quantisation quality loss, binary/int8 embeddings, Matryoshka

### Takeaway
Never run EmbeddingGemma (v1 or v2) in float16; use bf16 or fp32. This matters on MLX because mlx-embeddings' converter defaults to `--dtype float16`. Weight quantisation down to about 4 bits costs well under 1% retrieval quality in Jina's GGUF tests, while 1–2-bit quantisation collapses quality. On the output side, int8 embeddings are near-lossless, binary keeps about 92–96% (best with rescoring), and Matryoshka truncation is near-lossless to 256-d for EmbeddingGemma 2.

### Cited Findings
- EmbeddingGemma 2 model card: "Do not use `float16`." The activation range exceeds float16's dynamic range, which can produce NaN or *silently degraded* embeddings without an error. Use bf16, else fp32. — [EmbeddingGemma 2 model card](https://ai.google.dev/gemma/docs/embeddinggemma/model_card_2?hl=pt-br)
- Mirrors of the v1 card carry the shorter note that EmbeddingGemma activations do not support float16, and advise fp32 or bf16. — [HF mirror README](https://huggingface.co/lazyDataScientist/EmbeddingGemma/blob/main/README.md)
- mlx-embeddings convert defaults to `--dtype float16`. — [GitHub Blaizzy/mlx-embeddings](https://github.com/Blaizzy/mlx-embeddings)
- Qwen3-Embedding's card examples use float16 (Transformers, and TEI `--dtype float16`), so fp16 is the vendor's own path there. — [HF Qwen3-Embedding-0.6B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)
- **Weight quantisation quality (Jina v4 GGUF, mean NDCG@5 over 5 Nano-BEIR sets, my means of Jina's per-set numbers):**

  | Quantisation | Mean NDCG@5 | Change vs F16 |
  |---|---|---|
  | F16 | 0.616 | baseline |
  | Q8_0 | 0.612 | −0.6% |
  | Q4_K_M | 0.612 | −0.6% |
  | IQ3_M | 0.616 | about 0% |
  | Q2_K | 0.607 | −1.5% |
  | IQ2_XXS | 0.557 | −9.5% |
  | IQ1_M | 0.483 | −21.5% |
  | IQ1_S | 0.444 | −27.8% |

  — [Jina GGUF article](https://jina.ai/news/optimizing-ggufs-for-decoder-only-embedding-models)
- Google publishes QAT checkpoints for EmbeddingGemma v1 (e.g. `embeddinggemma-300m-qat-q8_0-unquantized`, `-qat-q4_0-unquantized`). The mlx-community 4-bit build was converted from the q4_0 QAT one. — [HF google/embeddinggemma-300m-qat-q8_0-unquantized](https://huggingface.co/google/embeddinggemma-300m-qat-q8_0-unquantized); [mlx-community README mirror](https://hg.istephan-squireso.workers.dev/mlx-community/embeddinggemma-300m-4bit/blob/main/README.md)
- **Output (embedding) quantisation:** sentence-transformers `quantize_embeddings` (since v2.6.0) supports binary and int8.
  - Binary keeps about 92.5% of retrieval performance without rescoring and about 96% with rescoring, with 32× smaller storage and up to about 25× faster search.
  - Int8 needs a calibration set, since it defines the buckets.
  - Recommended pattern: binary search, then int8 or fp32 rescoring.
  — [HF blog: embedding quantization](https://huggingface.co/blog/embedding-quantization); [sbert.net docs](https://sbert.net/examples/applications/embedding-quantization)
- Mixedbread reports that binary plus MRL keeps 95% or more of performance, and considers 512-d binary the sweet spot. — [mixedbread binary MRL](https://www.mixedbread.com/blog/binary-mrl)
- **Matryoshka:**
  - EmbeddingGemma 2 truncates 768 → 512/256/128 (then re-normalise). It is close to lossless down to 256, while 128 "degrades multimodal quality substantially". — [EmbeddingGemma 2 model card](https://ai.google.dev/gemma/docs/embeddinggemma/model_card_2?hl=pt-br)
  - Qwen3-Embedding supports any dimension from 32 to 1024. — [HF Qwen3-Embedding-0.6B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)
  - Jina v4 works well only at its trained dims; e.g. 131-d is much worse. — [Jina GGUF article](https://jina.ai/news/optimizing-ggufs-for-decoder-only-embedding-models)

### Inferences
- For Thorp's per-book distinctness and similarity use, storing 256-d (or 512-d) fp16/int8 vectors per sampled chunk is ample; binary is worth it only if the index grows to hundreds of millions of vectors.
- If EmbeddingGemma is converted to MLX locally, pass `--dtype bfloat16` explicitly and sanity-check outputs for NaN and for cosine agreement with the sentence-transformers reference on a few hundred chunks.
- Qwen3-Embedding needs left padding and last-token pooling. A wrong padding side in a hand-rolled MLX batch loop is a likely silent-quality bug (inference from the card's examples).

### Gaps
- No published MLX-specific quality-loss numbers for 4-bit affine/DWQ quantisation of Qwen3-Embedding or EmbeddingGemma.
- No source on whether EmbeddingGemma 2's fp16 problem also affects MLX's fp16 kernels specifically (it is a property of the activations, so likely yes).

## Rough time to embed ~1B tokens: M-series Mac versus rented RTX 4090 / H100 (300M and 600M models)

### Takeaway
On an H100, a ~0.6B encoder embeds 1B tokens in well under an hour for about $1.50 (Runpod's BGE-M3 figure). On a Mac, the same job is plausibly 6–25+ hours of full GPU time for a 600M model and roughly half that for a 300M model, and that time is taken directly from MLX training. Embedding a sample (e.g. 50–100M tokens) locally, or renting a GPU for the full billion, are both reasonable.

### Cited Findings
- **Runpod (14 Sep 2026), BGE-M3 (568M), 512-token passages, TEI, approximate:**

  | GPU | Texts/s | Cost per 1B input tokens |
  |---|---|---|
  | H100 SXM | ~1,240 | $1.53 |
  | H200 | ~1,345 | $1.85 |
  | RTX 6000 Ada | ~275 | $1.65 |
  | RTX A6000 | ~265 | $1.08 |
  | RTX A5000 | ~190 | $0.78 |

  The RTX 4090 is not in Runpod's embedding table. — [Runpod GPU embedding benchmark](https://www.runpod.io/blog/gpu-embedding-workloads-benchmark)
- Runpod: for Qwen3-Embedding-0.6B, vLLM beats TEI by a median 2.6× in bulk mode (8B: 2.9×). For BGE-M3 the two engines tie (1.08×). On consumer 4090/3090 the engines are near parity for 8B. — [Runpod](https://www.runpod.io/blog/gpu-embedding-workloads-benchmark)
- EmbeddingGemma-300m on CUDA: 1,678 docs/s (Bekko paper; the GPU and protocol are given in the paper's CUDA setup, and documents are NQ-length, not 512 tokens). — [Bekko paper](https://arxiv.org/html/2607.25180v1)
- Mac anchors are the M4 Max MPS docs/s and M2 Max MLX tok/s figures in the throughput section. — [Bekko paper](https://arxiv.org/html/2607.25180v1); [jakedahn/qwen3-embeddings-mlx](https://github.com/jakedahn/qwen3-embeddings-mlx)
- An earlier Thorp note (Vast lane) quotes about 1 h / $0.36 for a 9m training job on a 4090; this is project context, not an embedding figure. — internal memory file `vast-lane-idle-why.md`

### Inferences (my arithmetic from the cited anchors; order of magnitude only)
- **H100, 600M-class (BGE-M3 / Qwen3-0.6B):** 1,240 texts/s × 512 tokens ≈ 635K tok/s, so 1B tokens takes about **26 min**, about **$1.5** per Runpod. With vLLM, Qwen3-0.6B may be faster still (2.6× over TEI on the same card).
- **H100, 300M-class (EmbeddingGemma):** roughly 1.5–2× faster than 600M, so about **15 min**. Cost is under $1 plus setup overhead, which dominates.
- **RTX 4090:** no direct figure. Assuming it is similar to the RTX 6000 Ada (~275 texts/s × 512 ≈ 140K tok/s), 1B tokens takes about **2 h** for 600M and about **1–1.5 h** for 300M. At typical marketplace 4090 rates this is a few dollars, plus setup time.
- **M-series Mac, 600M-class:**
  - Optimistic (44K tok/s, MLX 4-bit, M2 Max claim): about **6.3 h**.
  - BGE-M3 MPS anchor (~78 docs/s; about 40K tok/s if documents fill 512 tokens, about 12K tok/s if about 150 tokens): about **7–23 h**.
  - E5-large M4 Max anecdote (3.1K tok/s): about **90 h**.
  - Planning figure: **roughly 10–25 h of full GPU** on a Max-class chip; longer on base or Pro chips with fewer GPU cores.
- **M-series Mac, 300M-class:** roughly half the 600M figure, so **5–12 h** of full GPU on a Max-class chip.
- **GPU sharing:** MLX has no priority scheduling between processes, so a concurrent embedding job slows training step by step. A previous Thorp measurement (memory `m6-training-throughput.md`) already identifies GPU sharing as a main source of waste. Workable options:
  - **(a)** Run embedding only in gaps between training runs.
  - **(b)** Embed a sample (for example 2–5 chunks of 512 tokens per book × tens of thousands of books ≈ 50–100M tokens, which is under 1–2 h locally at the anchors above).
  - **(c)** Run on CPU via ONNX/OpenVINO for small models. The Bekko paper reports OpenVINO CPU-on-Mac numbers, but I did not extract them.
  - **(d)** Rent a 4090 or H100 for the full billion tokens, where it costs dollars.

### Gaps
- No direct RTX 4090 embedding throughput figure for any of the target models.
- No Mac embedding figure with a stated tokens-per-document count, so the Mac estimates span about 4×.
- Hourly H100 and 4090 prices were not captured (Runpod's page showed template placeholders); the cost-per-1B-token figures come from Runpod's table.
