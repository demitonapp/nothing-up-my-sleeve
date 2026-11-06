# Decisions

Every choice the brief left open, one line each.

## Repository and tooling

- Repository root is `~/Source/Thorp` (the brief's `thorp/`); the package is `thorp/` inside it, built with hatchling so `uv run thorp` works.
- Python pinned to 3.12 with `.python-version`; `pytest` and `ruff` are in a `dev` dependency group, not runtime dependencies.
- Ruff selects E, F, I, B, UP and ignores E501, since `ruff format` owns line length (100) and a few docstring lines run over.
- `thorp/paths.py` (not in the layout) is the one place paths are decided; `THORP_DATA` and `THORP_LEDGER` override them so tests run in a temporary directory.
- `thorp/chinchilla.py` (not in the layout) holds the section 11 formula so the dashboard and README share it.
- `thorp id SPEC` was added to print a spec's run id without running it.
- `thorp ledger SQL [PARAMS...]` binds every `?` to the most recent finished run when no parameters are given (or to `--run ID`), so the section 10 query runs as written.

## Acquisition

- The User-Agent names the project and reads its contact from `THORP_CONTACT`; no personal email is hard-coded into the repository.
- Resolver language match is "the row's language is one of the catalogue row's `;`-separated languages", since a few catalogue rows list two.
- Title normalisation is NFKD, drop combining marks, lowercase, punctuation to spaces, collapse whitespace; CJK passes through unchanged.
- The author "surname" is the last word of the normalised author field; a row with no author is matched on title alone.
- Book ids are `pg<gutenberg id>` (for example `pg1342`), so the source is visible in every shard name and ledger row.
- Raw downloads are cached as `data/texts/gutenberg/{id}.txt`; stripping happens on read, so a better stripper never needs a re-fetch.
- The manifest `set` column is inferred from the list's filename (`hole` in the name means `hole-card`).
- Licence removal when there is no END marker cuts at the first line beginning "End of (the) Project Gutenberg" or "*** END OF" or "START: FULL LICENSE".
- `data/resolution.csv` holds every list fetched so far; refetching a list replaces only that list's rows.
- Overrides (`lists/overrides.csv`) pick the right volume or translation where the resolver chose wrongly: Thousand Nights vol. 1 (3435, not vol. 10), Herodotus vol. 1 (2707, not vol. 2), Divine Comedy Longfellow complete (1004, not Norton), Dhammapada Max Müller (2017), Nibelungenlied Needler (7321), Kalevala Kirby vol. 1 (25953), Consolation of Philosophy H. R. James (14328); and books whose Gutenberg title differs from the list: Tao Te Ching as Legge's "Tao Teh King" (216), Confessions of St. Augustine Pusey (3296), Grimm's Household Tales Hunt (5314), Maupassant "Original Short Stories" vol. 1 (3077), Poetic Edda as Thorpe's "Elder Eddas" (14726, Bellows is not on Gutenberg), Euclid as Casey's "First Six Books" (21076, Heath is not on Gutenberg), Montaigne Cotton complete (3600), Einstein's Relativity 30155 (5001 has no plain-text file).
- Not on Gutenberg in any edition found, so left unresolved: Mencius, Kojiki, Hojoki, the Kural, the Panchatantra (recipe) and Newton's Principia (hole card). Euclid (21076) resolves but Gutenberg has no plain-text file for it, so it is fetched as missing.
- Kept as the resolver chose although not the listed translation: Gilgamish (Langdon, not Thompson), Shah Nameh (a "Persian Literature" anthology), Kalevala, Social Contract (Cole), Aesop (Townsend selection), Nicomachean Ethics (8438).

## Tokeniser, shards and data

- Tokeniser id is SHA-1 of the sorted book ids; settings that differ from the defaults (vocab 16384, byte fallback, coverage 0.9995) are appended to the key, so another vocabulary on the same books is a different directory.
- SentencePiece is trained lossless: identity normalisation, no dummy prefix, extra whitespace kept, newline as a user-defined piece, digits split. `decode(encode(text)) == text`, so bits per byte charges for every byte, whitespace and line breaks included.
- SentencePiece samples at most 4 million lines (`input_sentence_size`) with `max_sentence_length=16384`; ids are unk 0, bos 1, eos 2, no pad.
- Byte-fallback rate per book (fraction of tokens that are byte pieces) is in `stats.json` beside bytes per token.
- Shards are written to a temporary name and renamed, so an interrupted write never leaves a half shard that would be "written once".
- Hole-card books are also sharded (under the run's tokeniser) so evaluation tokenises once; they are never in a recipe or in tokeniser training.
- `order: shuffled` means: books concatenated in a seeded shuffle per pass, cut into non-overlapping `context + 1` windows, and the windows themselves dealt in a seeded shuffle into batches. Without the window shuffle every batch would be 32 consecutive windows of one book.
- A window's family (for the per-batch family mix) is the family of the book its first token comes from; the mix is logged as `data/family/<family>` every 50 steps.
- The remainder of a pass that does not fill a batch is dropped.

## Model and training

- The "9m" preset as specified (6 layers, width 192) has 2.66M non-embedding and 3.34M embedding parameters (6.0M total, 16,384 × 192 token plus 1,024 × 192 position embeddings), not the brief's "about 6M non-embedding + 3M embedding". The layer and width table wins; N in the Chinchilla formula is the measured non-embedding count.
- A `tiny` preset (2 layers, width 64) exists for tests only.
- LayerNorm without bias, GELU (tanh approximation), initialisation N(0, 0.02) with output projections scaled by 1/√(2·layers).
- Attention uses `mx.fast.scaled_dot_product_attention` with a causal mask.
- "bf16 parameters with fp32 optimiser state": the model computes in bf16; the optimiser keeps an fp32 master copy of the weights plus fp32 Adam moments, and the bf16 weights are refreshed from the master after every step. Checkpoint `model.safetensors` holds the fp32 master.
- Weight decay (0.1) applies to every parameter, norms and embeddings included (MLX AdamW's default); no bias correction (MLX's default).
- Learning rate: linear warmup over 200 steps to 1e-3, then cosine to 1e-4 at the last step.
- The loss and its gradient are compiled with `mx.compile` (model state as inputs and outputs); clipping and the optimiser step run eagerly in fp32.
- Steps are numbered from 1 (step N is after N updates); evaluation runs at every multiple of `eval.every_steps` and at the final step; checkpoints at every multiple of `checkpoint.every_steps` and at the final step.
- `param_norm` is the L2 norm of the fp32 master weights; `grad_norm` is the pre-clip global norm.
- On resume, ledger rows recorded after the checkpoint step are deleted, so the metric series has no duplicates; wall time accumulates across resumes via `state.json`.
- A run that raises is marked `failed: <ExceptionType>` in `runs.status`.
- The git commit recorded is `HEAD`, with `-dirty` when tracked files have uncommitted changes.

## Evaluation

- Each held-out book is scored as `[EOS] + tokens + [EOS]`, so every token is predicted once with no free first token; `tokens` in the evals row is the number of predictions (book tokens + 1).
- Windows do not overlap; each starts with an empty context, which slightly overstates loss relative to a sliding window.
- Set means are unweighted means over books; `eval/<set>/ce_mean_en` and `bpb_mean_en` are the same over English books only, and the Chinchilla gap uses `ce_mean_en`.
- Missing hole cards are listed in the run's `eval_sets` artifact (`missing`) and in the run log, since the `runs` table has no column for them.
- Samples are stored as one `samples` artifact (JSON list of prompt, temperature, text) and one `top10` artifact per eval step; temperature sampling is seeded by the step.
- Determinism: on the GPU, MLX's embedding-gradient scatter-adds are not bitwise reproducible (about 1e-9 in fp32, 6e-5 in bf16), and Adam amplifies this, so two identical GPU runs drift apart. The resume test therefore runs on the CPU, where MLX is bitwise reproducible; the seed-2 run measures the run-to-run spread that matters.

## Dashboard and ledger

- The server adds `/api/run?run=` beside the three specified endpoints, for the headline, samples, top-10, recipe composition and tokeniser stats.
- Recipe composition, eval-set membership and the tokeniser path are written as artifacts at step 0 (`recipe`, `eval_sets`, `tokeniser`), and the parameter counts and token plan as `model/*` and `plan/*` metrics, so the ledger alone describes the run.
- The dashboard binds to 127.0.0.1 only.
- The headline's "tokens a second" is the mean over the last 50 steps; the estimated finish uses it.
- The smoke spec is `specs/smoke-10.yaml` with recipe `lists/smoke-10.csv` (the first 10 rows), rather than a "limit" key in the spec.
