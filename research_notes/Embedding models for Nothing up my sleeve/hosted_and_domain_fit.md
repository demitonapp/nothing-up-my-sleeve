# Hosted embedding APIs and domain fit for long pre-1930 literary prose (as of 12 Nov 2026)

## A1. Current hosted offerings: quality, context, dimensions, price, batch discounts

### Takeaway
The current hosted line-up is Gemini Embedding 2 (8,192-token input, $0.20/M, or $0.10/M batch), Voyage 4 (32K input, $0.02 to $0.12/M, 33% batch discount, and voyage-context-4 for chunks embedded with whole-document context), Cohere Embed 5 Pro/Fast (128K input, about $0.12/$0.08/M, from secondary sources only), and OpenAI text-embedding-3, which is unchanged since 2024 (8,192 input, $0.02/$0.13/M, 50% batch discount). None of them takes a whole book in one call. Only Cohere's 128K and voyage-context-4's 120K-per-request auto-chunking come close to a long chapter or a novella.

### Cited Findings
**Google**
- gemini-embedding-2: text at $0.20/M tokens standard and $0.10/M batch. Images are $0.45/M ($0.225 batch). Standard calls are free on the free tier, but free-tier data "may be used to improve Google's products". There is no batch on the free tier. — [Google AI Studio pricing](https://aistudio.google.com/docs/pricing)
- gemini-embedding-001 (text only): $0.15/M standard and $0.075/M batch. — [Google AI Studio pricing](https://aistudio.google.com/docs/pricing)
- gemini-embedding-2: max input 8,192 tokens, shared across modalities. Output dims are flexible from 128 to 3072 (default 3072, recommended 768/1536/3072), and truncated dims are renormalized automatically. There is no `task_type` parameter; you use a task prefix in the prompt instead. Latest update April 2026. Inputs over the limit are **silently truncated**. — [Google embeddings docs](https://aistudio.google.com/docs/embeddings)
- gemini-embedding-001: max input 2,048 tokens. Has `task_type` (SEMANTIC_SIMILARITY, CLUSTERING, RETRIEVAL_DOCUMENT and others). Embedding spaces of 001 and 2 are incompatible, so upgrading means re-embedding. — [Google embeddings docs](https://aistudio.google.com/docs/embeddings)
- Google's docs list MTEB scores by output dimension without naming the model: 2048 → 68.16, 1536 → 68.17, 768 → 67.99, 512 → 67.55, 256 → 66.19, 128 → 63.31. Below 768 dims the loss is small. — [Google embeddings docs](https://aistudio.google.com/docs/embeddings)
- Gemini Embedding (001) topped MTEB(Multilingual) at launch in March 2025. — [Gemini Embedding paper, arXiv 2503.07891](https://arxiv.org/pdf/2503.07891)
- Third-party trackers disagree on the Vertex AI price for Embedding 2: Costbench lists $0.25/M text ($0.125 batch) on Vertex. Release dates also differ between sources: 10 Mar 2026 (preview) and 22 Apr 2026 (GA). — [Costbench Vertex](https://www.costbench.com/software/embedding-apis/vertex-ai-embeddings/)

**Voyage AI (MongoDB)** (pricing page last updated 2026-09-29)
- voyage-4-large $0.12/M, voyage-4 $0.06/M, voyage-4-lite $0.02/M, voyage-context-4 $0.12/M, voyage-code-4 $0.12/M. Each comes with 200M free tokens. The Batch API is 33% off with a 12-hour window (about $0.08, $0.04 and $0.013/M), and free tokens do not apply to batch. Older models: voyage-3-large and voyage-context-3 $0.18/M, voyage-3.5 $0.06/M. — [Voyage pricing](https://docs.voyageai.com/docs/pricing)
- All 4-series models have 32,000-token context. Dims are 1024 by default, with 256, 512 and 2048 available. Quantised outputs: float, int8, uint8, binary, ubinary. The 4-series models share one compatible embedding space. voyage-4-nano is an open-weight model on Hugging Face in the same space. — [Voyage embeddings docs](https://docs.voyageai.com/docs/embeddings)
- voyage-context-4 embeds chunks of the same document together, so each chunk vector carries context from its document. Limits: 32K tokens per chunk, 120K total tokens per request with `enable_auto_chunking=True` (32K without it), at most 1,000 inputs and 16K chunks per request. Default auto chunk size is 512 tokens with no overlap. — [Voyage contextualized chunk docs](https://docs.voyageai.com/docs/contextualized-chunk-embeddings)
- An AWS Marketplace listing gives voyage-4-large "120K total tokens per request". That is the per-request batch limit, not the per-input context. — [AWS Marketplace](https://aws.amazon.com/marketplace/pp/prodview-pgzgeftmiyf6y)

**Cohere**
- Embed 5 (Pro and Fast) was released around 30 Sep 2026 (one source says 8 Oct). Both take 128K tokens of context and share one vector space, so Pro-built indexes can be queried with Fast. Secondary sources give text prices of Pro $0.12/M and Fast $0.08/M, and image tokens at $0.40/M (one says $0.50). — [DataNorth](https://datanorth.ai/news/cohere-releases-embed-5-pro-and-embed-5-fast); [Digital Applied, 30 Sep 2026](https://www.digitalapplied.com/blog/cohere-embed-5-pro-fast-embedding-models); [RuntimeWire](https://runtimewire.com/article/cohere-embed-5-retrieval-models); [Cloudprice](https://cloudprice.net/models/cohere-embed-5-pro)
- Cohere's own pricing page lists no per-token Embed price. It links to the Embed 5 announcement and otherwise points to sales and docs. It shows no batch discount. — [Cohere pricing](https://cohere.com/pricing)
- Embed v4 also had 128K input. It was priced at about $0.12/M on Bedrock, Azure and OCI, and was last published at $0.10/M by Cohere directly. — [Maxim/Bifrost Bedrock](https://www.getmaxim.ai/bifrost/llm-cost-calculator/provider/bedrock/model/cohere.embed-v4-0); [Kunal Ganglani](https://www.kunalganglani.com/embedding-prices/embed-v4)

**OpenAI**
- text-embedding-3-small and -large are still the current models; the docs mention no successor. Both take 8,192 max input tokens. Default dims are 1536 and 3072, with Matryoshka-style `dimensions` truncation. MTEB 62.3% and 64.6% respectively (old MTEB v1 numbers from 2024). — [OpenAI embeddings guide](https://developers.openai.com/api/docs/guides/embeddings)
- Price $0.02/M (small) and $0.13/M (large). The Batch API is 50% off. — [OpenRouter 3-large](https://openrouter.ai/openai/text-embedding-3-large/pricing); [Activepieces, checked Nov 2026](https://www.activepieces.com/blog/openai-embeddings-api-pricing-in-2026-dated-and-checked); [Futureagi 3-small, verified 6 Aug 2026](https://futureagi.com/llm-cost-calculator/openai/text-embedding-3-small)

**Others**
- Jina Embeddings v4 API is listed at about $0.02/M (aggregator, as of 2026-04-20). Jina's API also offers late chunking. — [pricepertoken Jina](https://pricepertoken.com/embedding/author/jina); [Jina late chunking blog](https://jina.ai/news/late-chunking-in-long-context-embedding-models/)
- Mistral Embed is described as the cheapest frontier list price, with 1024 dims and roughly 58.6 on an "illustrative" retrieval chart. Same chart: Cohere v4 about 61.5, Jina v4 about 60.0, Voyage-3 about 64.0, OpenAI 3-large about 64.6. The article is dated 4 May 2026 and its numbers are approximate. — [Digital Applied cost calculator](https://www.digitalapplied.com/blog/embedding-model-cost-calculator-vendor-comparison-2026)
- Open-weight leaders cited in 2025 include Llama-Embed-Nemotron-8B (top open model on MMTEB multilingual retrieval), Qwen3-Embedding-8B and EmbeddingGemma (best under 500M parameters). — [NVIDIA forum](https://forums.developer.nvidia.com/t/llama-embed-nemotron-8b-model-tops-the-multilingual-text-retrieval-leaderboard/348440); [EmbeddingGemma, arXiv 2509.20354](https://arxiv.org/pdf/2509.20354); [Modal MTEB article](https://modal.com/blog/mteb-leaderboard-article)

### Inferences
- On published benchmarks, Gemini Embedding 2, Voyage 4-large and Cohere Embed 5 Pro are the hosted top tier. OpenAI's 3-series is two years old and now mid-pack on quality, though 3-small is still the cheapest well-known option.
- Silent truncation at 8,192 tokens (Gemini 2) is a real hazard. A naive per-book call would embed only the opening pages, usually Gutenberg front matter and preface. Any per-book vector has to be built from chunks: mean-pooling, or contextual chunk embedding.
- For "distinctness" and "retelling" scores, consistent chunking and pooling probably matter more than the few MTEB points between vendors. A local open-weight model at about the same MTEB tier (Qwen3-Embedding-8B, EmbeddingGemma) can run over 1B tokens on owned or rented GPUs. That would be at least competitive; this is inferred, not measured.
- Voyage 4's shared space with open-weight voyage-4-nano is useful: bulk-embed locally with nano, then query with the hosted 4-series. Voyage claims the spaces are compatible; quality on this corpus is untested.

### Gaps
- The live MTEB v2 leaderboard ranking as of November 2026 could not be retrieved. No source dated Nov 2026 gave cross-vendor MTEB numbers, and the Embed 5 vs Voyage 4 vs Gemini 2 comparison article (MarkTechPost) returned 403.
- Cohere Embed 5 prices are unverified against a Cohere first-party page. Cohere's batch discount is unknown.
- Mistral Embed, Amazon Titan Text Embeddings v2 and Amazon Nova multimodal embeddings: no first-party price or context figure was retrieved in this pass.
- OpenAI prices come from aggregators rather than openai.com/pricing directly. They are consistent across sources and with long-standing list prices.

## A2. Cost to embed 1B tokens

### Takeaway
Embedding 1B tokens costs roughly $10 (OpenAI 3-small batch) to $200 (Gemini 2 standard). For top-tier quality it is about $65 to $100 with a batch API: OpenAI 3-large batch $65, Voyage 4-large batch about $80, Gemini 2 batch $100. These are small sums next to Nothing up my sleeve's GPU spend, so price should not decide the choice. Fit to the task and long-input handling should.

### Cited Findings
Arithmetic: 1,000M tokens × the list price per M, using the prices cited in A1.
- Gemini Embedding 2: $200 standard / $100 batch. gemini-embedding-001: $150 / $75. — [Google pricing](https://aistudio.google.com/docs/pricing)
- Voyage 4-large and voyage-context-4: $120 standard ($96 after the 200M free tokens) / about $80 batch. voyage-4: $60 ($48 after free tokens) / about $40 batch. voyage-4-lite: $20 / about $13. — [Voyage pricing](https://docs.voyageai.com/docs/pricing)
- OpenAI 3-large: $130 / $65 batch. 3-small: $20 / $10 batch. — [OpenRouter](https://openrouter.ai/openai/text-embedding-3-large/pricing); [Activepieces](https://www.activepieces.com/blog/openai-embeddings-api-pricing-in-2026-dated-and-checked)
- Cohere Embed 5 Pro about $120, Fast about $80 (unverified, no known batch tier). — [DataNorth](https://datanorth.ai/news/cohere-releases-embed-5-pro-and-embed-5-fast)
- Jina v4 about $20 (aggregator). — [pricepertoken](https://pricepertoken.com/embedding/author/jina)

### Inferences
- Tokens are counted with each vendor's own tokenizer, so "1B tokens" of Gutenberg text will bill differently per vendor. Archaic spelling and long-s OCR errors probably inflate token counts a little.
- Contextual chunk methods bill every token once (voyage-context-4). Overlapping sliding windows would multiply cost by the overlap factor.
- Batch tiers (12 to 24 hour turnaround) suit a one-off corpus build. Use standard endpoints for the search box's query-time embedding.

### Gaps
- Rate limits and throughput for 1B tokens per vendor (how many days a batch run takes) were not researched.

## B1. Long documents: whole books, chapters, long-context embedding

### Takeaway
No hosted model embeds a whole book (100K to 300K tokens) in one vector. The research consensus is to chunk, then either pool the chunks or make each chunk context-aware (late chunking, contextual chunk models), with RoPE-based models able to stretch their context without retraining. Benchmarks for long-document embedding are synthetic or retrieval-focused, not literary.

### Cited Findings
- The LongEmbed benchmark (EMNLP 2024) has 2 synthetic and 4 real long-document tasks. Training-free context extension (position interpolation) can extend existing embedding models "by several folds", and RoPE models gain more from NTK or SelfExtend than APE models do. — [LongEmbed, arXiv 2404.12096](https://arxiv.org/abs/2404.12096)
- Late chunking embeds the full text first and pools token vectors per chunk afterwards, so chunk embeddings reflect the whole document. It needs no training and works on any long-context model. v3 of the paper adds "long late chunking" for texts longer than the window, and reports gains over naive chunking across retrieval benchmarks. — [Late Chunking, arXiv 2409.04701](https://arxiv.org/html/2409.04701v3)
- State-of-the-art embedders struggle when retrieval needs context from the wider document (the ConTEB benchmark). The InSeNT contrastive post-training on top of late chunking improves this. — [arXiv 2505.24782](https://export.arxiv.org/pdf/2505.24782)
- voyage-context-4 is the hosted, productised version of this idea: chunks of the same document are embedded jointly, up to 120K tokens per request. — [Voyage docs](https://docs.voyageai.com/docs/contextualized-chunk-embeddings)
- Cohere Embed 5 accepts 128K tokens per input, the longest hosted window found. — [DataNorth](https://datanorth.ai/news/cohere-releases-embed-5-pro-and-embed-5-fast)

### Inferences
- For per-book distinctness, a book vector built as the mean or centroid of chapter embeddings (or a set of chunk vectors compared with a distribution distance) is standard practice and vendor-neutral. A single 128K-token vector would blur a long novel heavily even where a model allows it.
- Retelling and second-translation detection is better done at chunk level: align chapter or passage vectors across two books and score the share of chunks with a close match. Whole-book vectors would mostly catch topic, not textual correspondence.

### Gaps
- Found no benchmark that measures embedding quality on whole novels or chapters of literary prose specifically.

## B2. Historical / pre-1930 / literary English

### Takeaway
Direct evidence on modern embedding APIs for 19th-century English is thin. Historical-IR work warns that neural models lean on contemporary language patterns, and period-trained models (Living with Machines) improve historical tasks. No study was found that benchmarks Gemini, Voyage, Cohere or OpenAI on pre-1930 prose, so Nothing up my sleeve would need its own small eval.

### Cited Findings
- A retrieval benchmark built on the British Library BL19 collection (more than 35,000 works, 1700 to 1899) argues neural re-rankers rely on contemporary linguistic patterns, uses BM25 as its baseline, and notes that scarce relevance labels make fine-tuning risky. — [arXiv 2601.11874](https://arxiv.org/html/2601.11874v1)
- Living with Machines released BERT, word2vec and fastText models trained on 19th-century English books (CC BY 4.0). — [Hosseini et al., arXiv 2105.11321](https://arxiv.org/pdf/2105.11321v1.pdf)
- Historical BERT models trained on 19th-century books consistently improved time-sensitive word-sense disambiguation, most of all on older documents. — [ACL Findings 2021](https://preview.aclanthology.org/fix_video/2021.findings-acl.243.pdf)
- LLM prompt embeddings over Project Gutenberg excerpts encode literary origin well enough to classify passages by source with high accuracy. — [arXiv 2505.17071 (EMNLP 2025)](https://arxiv.org/html/2505.17071)

### Inferences
- Modern hosted models are trained on web-scale data that contains much Gutenberg and Wikisource text, so they are probably not badly off-domain for pre-1930 English. This is plausible but not evidenced by any benchmark found.
- A cheap guard: a 200 to 500 pair in-house eval (known retellings and translation pairs, plus same-author vs different-author chapters) run against 2 or 3 hosted APIs and 1 or 2 local models, before committing 1B tokens.

### Gaps
- No published comparison of hosted APIs on archaic or period English was found.

## B3. Near-duplicate, translation and paraphrase detection; style and authorship clustering

### Takeaway
General semantic embeddings are good at topic and paraphrase similarity but "consistently fail in stylistic tasks" (STEB). Authorship or style clustering therefore needs style-specific embeddings or stylometry, not MTEB leaders. Translation detection between languages is a well-trodden bitext-mining problem (LaBSE, LASER3 plus Vecalign), and it has been applied to book-level alignment of ancient texts with their translations.

### Cited Findings
- STEB (96 datasets, 7 languages: authorship verification and retrieval, AI-text detection, linguistic probing) finds semantic embeddings consistently fail at style tasks and no style embedding wins everywhere. — [STEB, arXiv 2606.31741](https://arxiv.org/abs/2606.31741)
- Authorship verification degrades most under temporal drift, among the shifts tested (AVShift benchmark). — [arXiv 2608.17979](https://arxiv.org/pdf/2608.17979)
- In a French literary study, embeddings captured authorial style features, and these persisted after LLM rewriting, measured through embedding dispersion. — [arXiv 2605.10606](https://arxiv.org/abs/2605.10606)
- Style-aware author and document representations evaluated on a Project Gutenberg literary corpus match or beat strong authorship-attribution baselines. — [arXiv 2407.13358](https://arxiv.org/pdf/2407.13358)
- Book- and chapter-level alignment of ancient Greek and Latin texts with their translations, using LaBSE similarity and Vecalign dynamic programming. — [CEUR Vol-3558](https://ceur-ws.org/Vol-3558/paper6193.pdf)
- Unsupervised bitext mining via dual-pivot transfer reaches state of the art. — [ACL 2022](https://aclanthology.org/2022.acl-long.595)

### Inferences
- For Nothing up my sleeve's "second translation of a held-out book" test: two English translations of the same foreign work are a monolingual paraphrase problem at passage level, and modern semantic embeddings should do well on it (inferred). Passage-alignment scoring in the Vecalign style would be stronger than whole-book cosine.
- Retellings, which share plot but differ in wording, are harder. They need chunk-level semantic matching, and style-insensitive semantic embeddings are an asset here.
- For "literary-style or authorship clustering", do not expect any hosted API to do well. Use style embeddings (from the STEB family) or classic stylometry, or report this as a known limit.

### Gaps
- No work was found on detecting English-to-English retellings or abridgements of public-domain books with embeddings.
- No evaluation of hosted 2026 APIs on STEB was retrieved (the abstract does not name the models tested).
