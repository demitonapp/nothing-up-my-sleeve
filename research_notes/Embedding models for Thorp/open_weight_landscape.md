# Open-weight text embedding models: the landscape as of November 2026

Research pass dated 2026-11-12. The live MTEB leaderboard (a Gradio space) was not fetched directly. The leaderboard figures below come from model cards and from one secondary snapshot dated 2026-10-14. Treat every rank as "as of" the date given.

## Which open-weight models lead MTEB English v2 / MMTEB, especially on retrieval, clustering and long documents?

### Takeaway
As of mid-October 2026, the open-weight leaders on MTEB English v2 are QZhou-Embedding (75.97) and Qwen3-Embedding-8B (75.22–75.23), with Qwen3-Embedding-4B (74.6) and the 0.6B Jasper-Token-Compression model (74.75) close behind. On multilingual MTEB v2 (MMTEB), Microsoft's harrier-oss-v1-27b (74.3, MIT) leads, followed by KaLM-Embedding-Gemma3-12B and NVIDIA llama-embed-nemotron-8b (non-commercial). I found no 2026 LongEmbed leaderboard numbers.

### Cited Findings
**Leaderboard snapshot (secondary source, leaderboard checked 2026-10-14, page updated 2026-10-15)**
- MTEB English v2, open-weight models: QZhou-Embedding 75.97 (listed rank 3), Jasper-Token-Compression-600M 74.75 (rank 2, MIT, about 0.6B), Qwen3-Embedding-8B 75.23 (rank 5), Qwen3-Embedding-4B 74.61 (rank 7), Qwen3-Embedding-0.6B 70.47. Ranks use the leaderboard's Borda aggregation, so they do not follow mean score. The closed ingot-8b-r3 was rank 1 at 75.98. — [FutureAGI blog](https://futureagi.com/blog/best-embedding-models-2025/)
- Older models on the same English v2 snapshot: NV-Embed-v2 69.81 (rank 24, CC BY-NC 4.0), stella_en_1.5B_v5 69.43 (rank 32), SFR-Embedding-2_R 69.82, e5-mistral-7b-instruct 67.97 (MIT), GritLM-7B 67.07, EmbeddingGemma-300m 69.67 (Gemma licence, 2,048 tokens). — [FutureAGI blog](https://futureagi.com/blog/best-embedding-models-2025/)
- MMTEB v2, 2026-10-14: harrier-oss-v1-27b ranks top at 74.27 (MIT, 27B, 32K). KaLM-Embedding-Gemma3-12B is rank 2 and llama-embed-nemotron-8b rank 3 (the page gives no scores for these two). Qwen3-Embedding-8B is rank 4. harrier-oss-v1-0.6b scores 69.01. — [FutureAGI blog](https://futureagi.com/blog/best-embedding-models-2025/)
- The harrier-oss-v1-27b model card gives MMTEB v2 74.3, embedding dimension 5,376, 32,768-token context and an MIT licence. Its architecture tag is gemma3_text. Siblings: harrier-oss-v1-0.6b (1,024 dimensions, 32K, 69.0) and harrier-oss-v1-270m (640 dimensions, 32K, 66.5). — [HF: microsoft/harrier-oss-v1-27b](https://huggingface.co/microsoft/harrier-oss-v1-27b)
- The llama-embed-nemotron-8b card reports Borda rank 1 on MTEB(Multilingual, v2) with a mean of 69.46. On the same card Qwen3-Embedding-8B has the higher mean, 70.58, at Borda rank 3. The card's snapshot date is not stated; the model was released 2025-10-21. This conflicts with the 2026-10-14 snapshot, where harrier has since overtaken both. — [HF: nvidia/llama-embed-nemotron-8b](https://huggingface.co/nvidia/llama-embed-nemotron-8b)
- Retrieval and clustering subscores on English v2, from the Qwen card (Qwen scores as of 2025-06-05):

| Model | Retrieval | Clustering |
|---|---|---|
| Qwen3-Embedding-8B | 69.44 | 58.57 |
| Qwen3-Embedding-4B | 68.46 | 57.51 |
| Qwen3-Embedding-0.6B | 61.83 | 54.05 |
| gemini-embedding-exp-03-07 (closed) | 64.35 | 59.39 |
| gte-Qwen2-7B-instruct | 58.09 | 58.97 |
| stella_en_1.5B_v5 | 52.42 | 57.06 |
| NV-Embed-v2 | 62.84 | 47.66 |
| GritLM-7B | 54.95 | 50.82 |

  — [HF: Qwen/Qwen3-Embedding-8B](https://huggingface.co/Qwen/Qwen3-Embedding-8B)
- Retrieval and clustering on MMTEB: Qwen3-8B 70.88 retrieval and 57.65 clustering; Qwen3-4B 69.60 and 57.15; Qwen3-0.6B 64.64 and 52.33; BGE-M3 54.60 and 40.88; NV-Embed-v2 56.72 and 40.80; multilingual-e5-large-instruct 57.12 and 50.75. — [HF: Qwen/Qwen3-Embedding-8B](https://huggingface.co/Qwen/Qwen3-Embedding-8B)
- Octen-Embedding-8B is a fine-tune of Qwen3-Embedding-8B and targets retrieval. Its team claims first place on RTEB; a third-party page gives 0.8045 as #1 on RTEB in January 2026. A later snapshot shows it at rank 3 on RTEB with 79.38 (2026-05-06). — [Octen blog](https://octen-team.github.io/octen_blog/posts/octen-rteb-first-place); [benchmarklist.com](https://benchmarklist.com/models/octen-embedding-8b/)
- An arXiv robustness study of multilingual embedding rankings found Octen-Embedding-8B "consistently" at the top rank of its best-performing cluster. — [arXiv 2605.31142](https://arxiv.org/pdf/2605.31142)
- LongEmbed (EMNLP 2024) has two synthetic tasks (passkey, needle) and four real ones: NarrativeQA, QMSum, SummScreenFD and 2WikiMultihopQA. It is integrated into MTEB. It found that RoPE-based models extend to long context better than absolute-position models, and that NTK scaling took E5-Mistral to 32K with state-of-the-art LongEmbed results at the time. — [arXiv 2404.12096](https://arxiv.org/html/2404.12096v3)
- Older numbers are still widely quoted: "NV-Embed-v2 69.32", "BGE-M3 63.0" and "nomic ~62" are from the old v1 English (56-task) board and do not compare with v2. — [PremAI, 2026-03-17](https://www.premai.io/blog/best-embedding-models-for-rag-2026-ranked-by-mteb-score-cost-and-self-hosting/); [hussain-nazary list](https://hussain-nazary.github.io/top-10-embedding-models-2026.html)

### Inferences
- English v2 is saturated at the top. Six open models sit between 74.6 and 76.0, and the gap between Qwen3-4B and Qwen3-8B (0.6 points) is smaller than the leaderboard's run-to-run noise. Parameter efficiency now separates the models more than raw score does. Jasper-Token-Compression-600M at 74.75 is the stand-out claim, but it needs checking.
- Thorp's work is English prose. NarrativeQA in LongEmbed (questions over whole books and scripts) is the most relevant public long-document task. Qwen3 retrieval scores (69.4 at 8B) are well ahead of NV-Embed-v2 and stella, which matters more than the overall mean.
- For clustering specifically, gte-Qwen2-7B and stella score about as well as Qwen3-4B. Clustering scores are bunched (54–59), so the choice of model matters less here than for retrieval.

### Gaps
- I could not fetch the live MTEB leaderboard (Gradio). No figures were verified directly for November 2026.
- I found no 2026 LongEmbed results for any model: no LongEmbed numbers on the Qwen3, harrier, jina v5 or EmbeddingGemma 2 cards as fetched.
- The QZhou-Embedding model card returned HTTP 401, so its parameter count, base model, context length and release date are unverified here. It is believed to be a Qwen2.5-7B-based model from Kingsoft (Aug 2025, [arXiv 2508.21632](https://arxiv.org/pdf/2508.21632)), but this pass did not read that report.
- I found no source for the KaLM-Embedding-Gemma3-12B score or licence, or for the Jasper-Token-Compression-600M specs.

## Specs of the serious candidates (parameters, dimension, Matryoshka, context, licence, release date)

### Takeaway
The permissive (Apache/MIT), long-context, Matryoshka-capable shortlist pool is: Qwen3-Embedding 0.6B/4B/8B (Apache, 32K, MRL), harrier-oss-v1 270m/0.6b/27b (MIT, 32K), EmbeddingGemma 2 (Apache, 8K, MRL, 270M text path) and BGE-M3 (MIT, 8K). Jina v5 and NVIDIA's top models are strong but non-commercial.

### Cited Findings
| Model | Params | Dim (MRL) | Context | Licence | Released | Headline score | Source |
|---|---|---|---|---|---|---|---|
| Qwen3-Embedding-8B | 8B, 36 layers | 4096 (MRL yes) | 32K | Apache 2.0 | paper 2025-06-05 | Eng v2 75.22; MMTEB 70.58 | [HF](https://huggingface.co/Qwen/Qwen3-Embedding-8B) |
| Qwen3-Embedding-4B | 4B, 36 layers | 2560 (MRL yes) | 32K | Apache 2.0 | 2025-06 | Eng v2 74.60; MMTEB 69.45 | [HF](https://huggingface.co/Qwen/Qwen3-Embedding-8B) |
| Qwen3-Embedding-0.6B | 0.6B, 28 layers | 1024 (MRL yes) | 32K | Apache 2.0 | 2025-06 | Eng v2 70.70; MMTEB 64.33 | [HF](https://huggingface.co/Qwen/Qwen3-Embedding-8B) |
| harrier-oss-v1-27b (Microsoft) | 27B (gemma3_text arch) | 5376 (MRL not stated) | 32,768 | MIT | not stated (2026) | MMTEB v2 74.3, top as of 2026-10-14 | [HF](https://huggingface.co/microsoft/harrier-oss-v1-27b); [FutureAGI](https://futureagi.com/blog/best-embedding-models-2025/) |
| harrier-oss-v1-0.6b | 0.6B | 1024 | 32,768 | MIT | not stated | MMTEB v2 69.0 | [HF](https://huggingface.co/microsoft/harrier-oss-v1-27b) |
| harrier-oss-v1-270m | 270M | 640 | 32,768 | MIT | not stated | MMTEB v2 66.5 | [HF](https://huggingface.co/microsoft/harrier-oss-v1-27b) |
| EmbeddingGemma 2 (Google DeepMind) | 740M total; text path 270M (130M transformer + 140M embedder); plus 170M vision and 300M audio | 768 (MRL 512/256/128) | 8,192 | Apache 2.0 | 2026-10-06 | Eng v2 68.46; MMTEB v2 61.36; MTEB Code 78.68 | [Google blog](https://blog.google/innovation-and-ai/technology/developers-tools/embeddinggemma-2/); [HF](https://huggingface.co/google/embeddinggemma-2) |
| EmbeddingGemma (v1) 300m | about 300M | 768 | 2,048 | Gemma licence | 2025-09 | Eng v2 69.67 (FutureAGI) | [FutureAGI](https://futureagi.com/blog/best-embedding-models-2025/); [arXiv 2509.20354](https://alphaxiv.org/abs/2509.20354) |
| jina-embeddings-v5-text-small | 677M (base Qwen3-0.6B-Base) | 1024 (MRL 32–1024) | 32,768 | CC BY-NC 4.0 | 2026-02-18 | Eng v2 71.7; MMTEB 67.7 (card); 67.0 (search snippet) | [HF](https://huggingface.co/jinaai/jina-embeddings-v5-text-small); [arXiv 2602.15547](https://arxiv.org/html/2602.15547v1) |
| jina-embeddings-v5-text-nano | 239M per Elastic's announcement, though its sizes appear swapped (see note) | n/a | 32K | CC BY-NC 4.0 | 2026-02 | Eng v2 71.0; MMTEB 65.5 | [HF](https://huggingface.co/jinaai/jina-embeddings-v5-text-nano); [Elastic PR](https://ir.elastic.co/news/news-details/2026/Elastic-Introduces-Best-in-Class-Embedding-Models-for-High-Performance-Semantic-Search/default.aspx) |
| llama-embed-nemotron-8b (NVIDIA) | 7.5B (Llama-3.1-8B, bidirectional) | 4096 (MRL not mentioned) | 32,768 | non-commercial/research only (NVIDIA licence plus Llama 3.1) | 2025-10-21 | MMTEB v2 mean 69.46, Borda #1 at card time | [HF](https://huggingface.co/nvidia/llama-embed-nemotron-8b) |
| NV-Embed-v2 | 7.85B | 4096 | 32,768 | CC BY-NC 4.0 | 2024 | Eng v2 69.81 | [PremAI](https://www.premai.io/blog/best-embedding-models-for-rag-2026-ranked-by-mteb-score-cost-and-self-hosting/); [Qwen card](https://huggingface.co/Qwen/Qwen3-Embedding-8B) |
| Octen-Embedding-8B | 8B (Qwen3-Embedding-8B fine-tune) | n/a | n/a | n/a | about 2026-01 | RTEB #1 (Jan 2026), #3 (May 2026) | [Octen blog](https://octen-team.github.io/octen_blog/posts/octen-rteb-first-place); [benchmarklist](https://benchmarklist.com/models/octen-embedding-8b/) |
| BGE-M3 (BAAI) | 568M | 1024; outputs dense, sparse and ColBERT multi-vector | 8,192 | MIT | 2024 | MMTEB 59.56; clustering 40.88 | [PremAI](https://www.premai.io/blog/best-embedding-models-for-rag-2026-ranked-by-mteb-score-cost-and-self-hosting/); [Qwen card](https://huggingface.co/Qwen/Qwen3-Embedding-8B); [BentoML](https://www.bentoml.com/blog/a-guide-to-open-source-embedding-models) |
| jina-embeddings-v3 | 570M | 1024 (MRL to 32) | 8,192 | CC BY-NC 4.0 | 2024 | about 62 (v1 board) | [PremAI](https://www.premai.io/blog/best-embedding-models-for-rag-2026-ranked-by-mteb-score-cost-and-self-hosting/) |
| nomic-embed-text-v1.5 | 137M | 768 (MRL to 64) | 8,192 | Apache 2.0 | 2024 | about 62 (v1 board) | [PremAI](https://www.premai.io/blog/best-embedding-models-for-rag-2026-ranked-by-mteb-score-cost-and-self-hosting/) |
| mxbai-embed-large | 335M | 1024 | 512 | Apache 2.0 | 2024 | n/a | [hussain-nazary](https://hussain-nazary.github.io/top-10-embedding-models-2026.html) |
| stella_en_1.5B_v5 | 1.5B | n/a | n/a | n/a | 2024 | Eng v2 69.43 | [Qwen card](https://huggingface.co/Qwen/Qwen3-Embedding-8B) |
| gte-Qwen2-7B-instruct | 7B | n/a | n/a | n/a | 2024 | Eng v2 70.72; clustering 58.97 | [Qwen card](https://huggingface.co/Qwen/Qwen3-Embedding-8B) |
| F2LLM-v2-14B | about 14B | n/a | n/a | Apache 2.0 | n/a | only Scandinavian v1 71.10 reported | [FutureAGI](https://futureagi.com/blog/best-embedding-models-2025/) |

- Jina parameter-count conflict: the Hugging Face card gives v5-text-small as 677M. Elastic's press release gives "small 239M, nano 677M", which looks swapped. The Hugging Face card is more likely correct. — [HF](https://huggingface.co/jinaai/jina-embeddings-v5-text-small); [Elastic](https://ir.elastic.co/news/news-details/2026/Elastic-Introduces-Best-in-Class-Embedding-Models-for-High-Performance-Semantic-Search/default.aspx)
- Jina v5-omni (2026-05-12) extends v5-text to images, audio and video. Its text embeddings are identical to v5-text and it is also CC BY-NC 4.0. — [Jina news](https://jina.ai/news/jina-embeddings-v5-omni-multimodal-embeddings-for-text-image-audio-and-video)
- NVIDIA also lists llama-nemotron-embed-1b-v2 as cleared for commercial use (text retrieval), but this pass found no scores for it. — [HF nemotron card](https://huggingface.co/nvidia/llama-embed-nemotron-8b)
- EmbeddingGemma 2 Matryoshka retention: English v2 68.46 at 768d, 68.41 at 512d, 67.78 at 256d and 65.68 at 128d. — [HF](https://huggingface.co/google/embeddinggemma-2)
- EmbeddingGemma 2 on-device use (quantized, Pixel 11 Pro): about 191MB RAM text-only, about 567MB with all modalities. It is built on the Gemma 4 architecture. — [Google blog](https://blog.google/innovation-and-ai/technology/developers-tools/embeddinggemma-2/). One secondary source said "Gemma 2"; the official blog says Gemma 4.

### Inferences
- If commercial use or redistribution of derived vectors matters, rule out jina v5, NV-Embed-v2 and llama-embed-nemotron-8b (all non-commercial). The project is personal research on public-domain text, so non-commercial terms may be acceptable, but this is a project decision.
- Whole-book and long-chunk work favours 32K-context models: Qwen3, harrier and jina v5. EmbeddingGemma 2 (8K) and BGE-M3 (8K) need chunking for anything over about 6,000 words.
- A plausible five to compare: Qwen3-Embedding-4B (or 8B), Qwen3-Embedding-0.6B, harrier-oss-v1-0.6b (or 27b if compute allows), EmbeddingGemma 2 and BGE-M3 as the classic baseline. Jina v5-text-small is a sixth if NC terms are acceptable. This is my synthesis, not a source's recommendation.

### Gaps
- Not verified in this pass: specs and 2026 status for Nomic Embed v2/v3, Snowflake Arctic Embed 2.x, newer mxbai models, IBM Granite Embedding (R2), ModernBERT-based embedders (gte-modernbert, nomic-modernbert), any newer BAAI model, Stella/Jasper specs, and KaLM-Embedding-Gemma3-12B details. I found no primary page for these.
- harrier-oss-v1 release date and Matryoshka support are not on the card as fetched.
- Octen dimensions, context and licence are not confirmed from a primary card.

## What is new in 2026 (Jan–Nov) and what changed from 2025?

### Takeaway
The 2026 releases are jina-embeddings-v5-text (Feb) and v5-omni (May), Octen-Embedding-8B (about Jan), Microsoft harrier-oss-v1 (date unconfirmed, top of MMTEB by Oct) and EmbeddingGemma 2 (Oct 6). I found no Qwen embedding successor; Qwen3.5 (Feb 2026) shipped no embedding model in any source I found. The 2026 trends are distillation of small models from 4–8B teachers, multimodal "omni" embedders, longer context on small models (8K–32K), and permissive licences replacing custom ones (Gemma licence to Apache).

### Cited Findings
- jina-embeddings-v5-text: released 2026-02-18, distilled from a 4B teacher into sub-1B models. — [Jina news](https://jina.ai/news/jina-embeddings-v5-text-distilling-4b-quality-into-sub-1b-multilingual-embeddings); [HF](https://huggingface.co/jinaai/jina-embeddings-v5-text-small)
- jina-embeddings-v5-omni: 2026-05-12, text, image, audio and video. — [Jina news](https://jina.ai/news/jina-embeddings-v5-omni-multimodal-embeddings-for-text-image-audio-and-video)
- EmbeddingGemma 2: 2026-10-06. It moves from the restrictive Gemma licence (v1) to Apache 2.0, from 2K to 8K context, and adds multimodality. Multilingual text is essentially flat (61.36 vs 61.15); code improves sharply (78.68 vs 68.76). — [Google blog](https://blog.google/innovation-and-ai/technology/developers-tools/embeddinggemma-2/); [HF](https://huggingface.co/google/embeddinggemma-2); [mixed-news](https://mixed-news.com/en/?p=35906)
- Octen-Embedding-8B: claimed RTEB #1 in January 2026. — [Octen blog](https://octen-team.github.io/octen_blog/posts/octen-rteb-first-place)
- harrier-oss-v1 (Microsoft, MIT): leads MMTEB v2 at 74.27 as of 2026-10-14, displacing the 2025 leaders Qwen3-8B (70.58) and llama-embed-nemotron-8b. — [FutureAGI](https://futureagi.com/blog/best-embedding-models-2025/); [HF](https://huggingface.co/microsoft/harrier-oss-v1-27b)
- Qwen3.5 (Feb 2026) and Qwen3.6-27B (Apr 2026) are generative models. No Qwen3.5 embedding release was found. — [Alibaba](https://www.alibabagroup.com/document-1960233590314762240); search summary (no embedding variant found)
- Qwen3-Embedding-8B (June 2025) still ranks in the top five on English v2 in October 2026. — [FutureAGI](https://futureagi.com/blog/best-embedding-models-2025/)

### Inferences
- The Qwen3-Embedding family has aged well. Many 2026 entrants (jina v5, Octen, probably harrier-0.6b) are built on Qwen3 or Gemma 3 backbones, so their gains over Qwen3 on English text are small.
- For English-only prose, the 2026 releases mostly add efficiency and licence options, not a big jump in quality.

### Gaps
- Exact release dates for harrier-oss-v1, KaLM-Embedding-Gemma3-12B, Jasper-Token-Compression-600M and F2LLM-v2.
- Whether Nomic, Snowflake, mixedbread, IBM or BAAI shipped new embedders in 2026. I found no evidence either way.

## Is there evidence on quality for literary, historical or archaic English text?

### Takeaway
There is thin, indirect evidence that modern embedders hold up on historical text: high embedding similarity across archaic and modern spellings in a 17th-century Italian study. I found no benchmark that scores current MTEB leaders on pre-1930 English fiction. The closest resources are a 19th-century British Library (BL19) retrieval benchmark and a 2026 LREC study of Danish historical newspapers, which found that the best model depends on the task.

### Cited Findings
- 17th-century Italian: embedding similarity stays robust (at least 0.85) across datasets even where language models struggle to generate historical text. The authors report that encoding cost is uncorrelated with embedding quality. — [arXiv 2606.27275](https://arxiv.org/pdf/2606.27275)
- A benchmark built on the British Library BL19 collection (19th-century fiction and non-fiction) uses expert queries and paragraph-level relevance labels to study change in language and terminology in retrieval. Model scores were not extracted in this pass (PDF unreadable). — [CEUR-WS Vol-4240 paper 45](https://ceur-ws.org/Vol-4240/paper45.pdf)
- LREC 2026: three historical benchmark tasks on 19th-century Danish newspapers; the best embedding model depends on the task. — [AAU / LREC 2026](https://vbn.aau.dk/ws/files/833312723/2026.lrec2026-1.287.pdf); [ACL preview](https://preview.aclanthology.org/ingest-lrec/2026.lrec-main.287/)
- Semantic search on 18th-century texts was evaluated in "Matching Meaning at Scale". Details were not extracted. — [alphaXiv 2605.09236](https://www.alphaxiv.org/abs/2605.09236.md)
- The "Cultural Analytics for Good" paper notes that historical IR evaluation frameworks are lacking. — [2601.11874](https://fugumt.com/fugumt/paper_check/2601.11874v1_enmode)
- Older work: historical language models improve time-sensitive disambiguation on 19th-century English books. — [ACL Findings 2021](https://preview.aclanthology.org/fix_video/2021.findings-acl.243.pdf)
- LongEmbed's NarrativeQA task (questions over full books and scripts, many of them Gutenberg texts) is the nearest standard long-literary retrieval task. — [arXiv 2404.12096](https://arxiv.org/html/2404.12096v3)

### Inferences
- Thorp should run its own small evaluation: translation pairs, multiple editions of the same work, and known near-duplicates from Gutenberg. Public benchmarks do not cover the task. The Danish result ("best model depends on task") argues for testing at least three or four candidates rather than trusting MTEB rank.
- Pre-1930 English is much closer to modern English than 17th-century Italian is to modern Italian. Given the robustness result, archaic spelling is probably a smaller risk than chunking strategy and context length for whole-book scores.

### Gaps
- No model scores from the BL19 benchmark paper; the PDF could not be parsed here.
- No published evaluation of Qwen3, harrier, EmbeddingGemma 2 or jina v5 on historical English found.
