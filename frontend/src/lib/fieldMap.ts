// The field's discoveries on two axes (13 November, Justin: "build the 2 axis into this page ... a card for the two
// axis and then when clicking in we have cards for the level below them"). One list of discoveries, each tagged on
// both axes, so an axis page and its category pages are views of the same list and cannot disagree:
//
// - Axis 1, the kind of claim: a law (how it scales), a mechanism (what inside does it), a representation (how it
//   is encoded), a behaviour (what it does from outside), a limit (what it fails at), a recipe (what produces it),
//   a measurement (how we know, and when we are fooled).
// - Axis 2, the object of study: training and scale, architecture, data, post-training, inference, internals,
//   knowledge, evaluation, safety.
//
// Written from the literature as known in mid-2026; each entry names its source. `thorp` points at where this
// project measures the same thing, when it does.

import { DEMITON_DISCOVERIES as DB, QWEN4B_PAGE } from './discoveryPaths';

export interface MapCategory { key: string; name: string; question: string; about: string }
export interface MapAxis { key: string; slug: string; n: number; name: string; question: string; about: string; categories: MapCategory[] }
export interface FieldDiscovery {
  key: string;
  title: string;
  finding: string;
  source: string;
  kind: string; // a category of the kind-of-claim axis
  object: string; // a category of the object-of-study axis
  thorp?: { href: string; label: string };
}

export const KINDS: MapCategory[] = [
  { key: 'law', name: 'Laws', question: 'How does it change with scale?', about: 'Regularities that hold across sizes, data and compute: what you can predict before you train.' },
  { key: 'mechanism', name: 'Mechanisms', question: 'What inside the network does it?', about: 'The heads, circuits and layers that carry out a behaviour, found by taking the network apart.' },
  { key: 'representation', name: 'Representations', question: 'How is it encoded?', about: 'The geometry of what a model knows: directions, features and maps in its hidden state.' },
  { key: 'behaviour', name: 'Behaviours', question: 'What does the model do, seen from outside?', about: 'Abilities and habits observed from prompts and answers alone, whatever does them inside.' },
  { key: 'limit', name: 'Limits', question: 'What does it reliably fail at?', about: 'Failures that recur across models and sizes, and what they say about how the models work.' },
  { key: 'recipe', name: 'Recipes', question: 'What procedure produces it?', about: 'Methods that make a model better, cheaper or more useful: architectures, data and training procedures.' },
  { key: 'measurement', name: 'Measurement', question: 'How do we know, and when are we fooled?', about: 'How readings are taken, and the ways a metric or a benchmark misleads.' },
];

export const OBJECTS: MapCategory[] = [
  { key: 'training', name: 'Training and scale', question: 'What happens as a model is trained, and grown?', about: 'Scaling, training dynamics, optimisation and the hyperparameters that carry across sizes.' },
  { key: 'architecture', name: 'Architecture', question: 'What is the network built from?', about: 'Attention and its variants, positions, feed-forward layers, experts and the sub-quadratic models.' },
  { key: 'data', name: 'Data', question: 'What does it read, and how much?', about: 'Quality, quantity, repetition, synthetic text and the tokeniser that cuts it up.' },
  { key: 'post-training', name: 'Post-training', question: 'How is a base model made into an assistant?', about: 'Instruction tuning, preference learning and what they do to a model besides.' },
  { key: 'inference', name: 'Inference and prompting', question: 'What changes at the moment of use?', about: 'In-context learning, chains of thought, test-time compute and faster decoding.' },
  { key: 'internals', name: 'Internals', question: 'What is going on inside?', about: 'Heads, circuits, features and directions: the network read as a machine.' },
  { key: 'knowledge', name: 'Knowledge and memory', question: 'What does it know, and can it put facts together?', about: 'Where facts are stored, how much fits, and whether two of them can be chained.' },
  { key: 'evaluation', name: 'Evaluation', question: 'Are the readings sound?', about: 'Benchmarks, contamination, judges and the metrics that make a curve look sudden.' },
  { key: 'safety', name: 'Safety and security', question: 'Where can it be made to misbehave?', about: 'Jailbreaks, backdoors, privacy and alignment that is shallower than it looks.' },
];

export const AXES: MapAxis[] = [
  { key: 'kind', slug: 'kind-of-claim', n: 1, name: 'Kind of claim', question: 'What sort of thing does the discovery say?', about: 'A law, a mechanism, a representation, a behaviour, a limit, a recipe or a measurement: the same finding means something different in each.', categories: KINDS },
  { key: 'object', slug: 'object-of-study', n: 2, name: 'Object of study', question: 'What is the discovery about?', about: 'Training and scale, architecture, data, post-training, inference, internals, knowledge, evaluation or safety.', categories: OBJECTS },
];

const CHAINING = { href: `${DB}/tests?test=chaining`, label: 'chaining two facts' };
const STARS = { href: `${DB}/stars`, label: 'our stars, lit by size' };

export const DISCOVERIES: FieldDiscovery[] = [
  // training and scale
  { key: 'power-law-scaling', title: 'Loss scales as a power law', finding: 'Test loss falls smoothly as a power law in parameters, data and compute, over many orders of magnitude.', source: 'Kaplan et al. 2020', kind: 'law', object: 'training' },
  { key: 'compute-optimal', title: 'Compute-optimal training', finding: 'For a fixed compute budget, parameters and tokens should grow together: about 20 tokens a parameter (Chinchilla).', source: 'Hoffmann et al. 2022', kind: 'law', object: 'training' },
  { key: 'double-descent', title: 'Double descent', finding: 'Test error can rise and then fall again as models, or training, grow past the point where they fit the data exactly.', source: 'Nakkiran et al. 2019', kind: 'law', object: 'training' },
  { key: 'grokking', title: 'Grokking', finding: 'A network can generalise long after it has memorised its training set, with nothing in the training loss to show it coming.', source: 'Power et al. 2022', kind: 'behaviour', object: 'training' },
  { key: 'emergent-abilities', title: 'Emergent abilities', finding: 'Some tasks sit at chance until a scale threshold, then jump.', source: 'Wei et al. 2022', kind: 'behaviour', object: 'training' },
  { key: 'mup', title: 'Hyperparameters transfer across sizes', finding: 'Under the maximal-update parametrisation, learning rates tuned on a small model carry over to a large one.', source: 'Yang et al. 2022', kind: 'recipe', object: 'training' },
  { key: 'distillation', title: 'Distillation', finding: 'A small model trained on a large one\'s output distribution learns more than from the labels alone; most strong small models are made this way.', source: 'Hinton et al. 2015', kind: 'recipe', object: 'training' },
  { key: 'implicit-reasoners', title: 'Grokked transformers reason implicitly', finding: 'Trained long enough, a transformer learns to compose two facts without writing the middle step, but only when the data has the right ratio of inferred to stated facts.', source: 'Wang et al. 2024', kind: 'behaviour', object: 'training', thorp: CHAINING },
  // architecture
  { key: 'transformer', title: 'The Transformer', finding: 'Attention alone, without recurrence, trains faster and better, and became the base of every large language model.', source: 'Vaswani et al. 2017', kind: 'recipe', object: 'architecture' },
  { key: 'rope', title: 'Rotary positions', finding: 'Encoding position as a rotation of queries and keys gives relative positions for free and extends to longer contexts.', source: 'Su et al. 2021', kind: 'recipe', object: 'architecture' },
  { key: 'glu', title: 'Gated feed-forward layers', finding: 'Gated linear units (SwiGLU) in the feed-forward layer improve quality at the same compute.', source: 'Shazeer 2020', kind: 'recipe', object: 'architecture' },
  { key: 'gqa', title: 'Shared keys and values', finding: 'Many query heads can share a few key-value heads (multi-query, grouped-query attention) at little cost in quality and a large saving in memory.', source: 'Shazeer 2019; Ainslie et al. 2023', kind: 'recipe', object: 'architecture' },
  { key: 'moe', title: 'Mixture of experts', finding: 'Routing each token to a few of many feed-forward experts adds capacity without adding compute a token.', source: 'Fedus et al. 2021', kind: 'recipe', object: 'architecture' },
  { key: 'subquadratic', title: 'Sub-quadratic sequence models', finding: 'State-space models and linear attention (Mamba, DeltaNet) run in linear time; the field has settled on hybrids that keep some full attention layers.', source: 'Gu & Dao 2023; Yang et al. 2024', kind: 'recipe', object: 'architecture' },
  { key: 'flash-attention', title: 'IO-aware attention', finding: 'Computing attention in tiles that fit the GPU\'s fast memory makes it several times faster and exact, which changed what context lengths are practical.', source: 'Dao et al. 2022', kind: 'recipe', object: 'architecture' },
  // data
  { key: 'textbook-quality', title: 'Quality beats quantity', finding: 'Textbook-grade and synthetic teaching data let small models match much larger ones on reasoning and code.', source: 'Gunasekar et al. 2023', kind: 'recipe', object: 'data' },
  { key: 'tinystories', title: 'Tiny models on simple text', finding: 'Models of a few million parameters write coherent, grammatical English when their training text is simple enough.', source: 'Eldan & Li 2023', kind: 'recipe', object: 'data' },
  { key: 'dedup', title: 'Deduplication', finding: 'Removing near-duplicate text improves models and cuts how much they memorise verbatim.', source: 'Lee et al. 2021', kind: 'recipe', object: 'data' },
  { key: 'data-constrained', title: 'Repeated data still counts', finding: 'Up to about four epochs, repeated tokens are worth nearly as much as new ones; past that their value decays.', source: 'Muennighoff et al. 2023', kind: 'law', object: 'data' },
  { key: 'model-collapse', title: 'Model collapse', finding: 'Training generation after generation on model-written text loses the tails of the distribution.', source: 'Shumailov et al. 2024', kind: 'limit', object: 'data' },
  { key: 'glitch-tokens', title: 'Glitch tokens', finding: 'Tokens that are common in the tokeniser\'s text but rare in training are barely learned, and the model misbehaves on them.', source: 'Rumbelow & Watkins 2023', kind: 'limit', object: 'data' },
  // post-training
  { key: 'rlhf', title: 'Learning from human preferences', finding: 'Fine-tuning on human preference rankings with a learned reward makes a much smaller model preferred to a much larger base one.', source: 'Ouyang et al. 2022', kind: 'recipe', object: 'post-training' },
  { key: 'dpo', title: 'Direct preference optimisation', finding: 'The preference objective can be optimised directly on pairs of answers, without a reward model or reinforcement learning.', source: 'Rafailov et al. 2023', kind: 'recipe', object: 'post-training' },
  { key: 'constitutional', title: 'Constitutional training', finding: 'A model can be trained to critique and revise its own answers against written principles, replacing much of the human labelling.', source: 'Bai et al. 2022', kind: 'recipe', object: 'post-training' },
  { key: 'superficial-alignment', title: 'Alignment is mostly style', finding: 'A thousand well-chosen examples are enough to make a base model a capable assistant: capability comes from pretraining.', source: 'Zhou et al. 2023', kind: 'behaviour', object: 'post-training' },
  { key: 'sycophancy', title: 'Sycophancy', finding: 'Models trained on human preferences learn to agree with the user, even against the truth.', source: 'Sharma et al. 2023', kind: 'limit', object: 'post-training' },
  // inference and prompting
  { key: 'in-context-learning', title: 'In-context learning', finding: 'A large enough model learns a new task from a few examples in its prompt, with no change to its weights.', source: 'Brown et al. 2020', kind: 'behaviour', object: 'inference' },
  { key: 'icl-gradient-descent', title: 'In-context learning as gradient descent', finding: 'On simple tasks, attention layers can carry out steps of gradient descent on the examples in the prompt.', source: 'von Oswald et al. 2023', kind: 'mechanism', object: 'inference' },
  { key: 'labels-format', title: 'The format matters more than the labels', finding: 'In-context examples work nearly as well with random labels: the model reads the task\'s form more than its answers.', source: 'Min et al. 2022', kind: 'behaviour', object: 'inference' },
  { key: 'chain-of-thought', title: 'Chain of thought', finding: 'Asking for intermediate steps improves multi-step answers sharply, at sufficient scale.', source: 'Wei et al. 2022', kind: 'behaviour', object: 'inference' },
  { key: 'zero-shot-cot', title: 'Thinking step by step', finding: 'The bare instruction to think step by step brings much of the gain of worked examples.', source: 'Kojima et al. 2022', kind: 'behaviour', object: 'inference' },
  { key: 'self-consistency', title: 'Self-consistency', finding: 'Sampling several chains of thought and taking the majority answer beats a single greedy chain.', source: 'Wang et al. 2022', kind: 'recipe', object: 'inference' },
  { key: 'test-time-compute', title: 'Test-time compute scales', finding: 'Reinforcement learning on checkable answers produces long reasoning traces whose accuracy grows with the thinking budget.', source: 'OpenAI 2024; DeepSeek-AI 2025', kind: 'law', object: 'inference' },
  { key: 'unfaithful-cot', title: 'Chains of thought can be unfaithful', finding: 'The stated reasoning is not always why the model answered: biasing features change answers without being mentioned.', source: 'Turpin et al. 2023', kind: 'limit', object: 'inference' },
  { key: 'lost-in-the-middle', title: 'Lost in the middle', finding: 'Facts in the middle of a long context are recalled worst; the start and the end are read best.', source: 'Liu et al. 2023', kind: 'limit', object: 'inference' },
  { key: 'steering', title: 'Steering by adding activations', finding: 'Adding a direction to the hidden state at inference changes the model\'s behaviour without retraining.', source: 'Turner et al. 2023', kind: 'recipe', object: 'inference' },
  { key: 'function-vectors', title: 'Function vectors', finding: 'An in-context task compresses into a single vector, which can be added to another prompt to run the task there.', source: 'Todd et al. 2023; Hendel et al. 2023', kind: 'representation', object: 'inference' },
  { key: 'speculative-decoding', title: 'Speculative decoding', finding: 'A small model drafts tokens and the large one checks them in parallel: the same output, several times faster.', source: 'Leviathan et al. 2023', kind: 'recipe', object: 'inference' },
  { key: 'outlier-features', title: 'Outlier features', finding: 'Past a few billion parameters a handful of hidden dimensions take huge values, which naive 8-bit quantisation breaks.', source: 'Dettmers et al. 2022', kind: 'representation', object: 'inference' },
  // internals
  { key: 'induction-heads', title: 'Induction heads', finding: 'A pair of heads, a previous-token head and an induction head, copies what followed an earlier occurrence of the current token; they form in a phase change that coincides with in-context learning.', source: 'Olsson et al. 2022', kind: 'mechanism', object: 'internals', thorp: STARS },
  { key: 'ioi-circuit', title: 'The indirect-object circuit', finding: 'A circuit of name-mover, S-inhibition and duplicate-token heads completes "John gave a drink to ..." with the right name.', source: 'Wang et al. 2022', kind: 'mechanism', object: 'internals' },
  { key: 'successor-heads', title: 'Successor heads', finding: 'Heads that increment ordinal sequences (Monday to Tuesday, 3 to 4) recur across models and sizes.', source: 'Gould et al. 2023', kind: 'mechanism', object: 'internals' },
  { key: 'copy-suppression', title: 'Copy suppression', finding: 'Heads that lower the probability of tokens already predicted earlier in the context, keeping the model from repeating itself.', source: 'McDougall et al. 2023', kind: 'mechanism', object: 'internals' },
  { key: 'retrieval-heads', title: 'Retrieval heads', finding: 'A small, universal set of heads does most of the work of fetching facts from long contexts; prune them and recall fails.', source: 'Wu et al. 2024', kind: 'mechanism', object: 'internals' },
  { key: 'attention-sinks', title: 'Attention sinks', finding: 'Models park unused attention on the first token; keeping it lets a model stream past its training length.', source: 'Xiao et al. 2023', kind: 'mechanism', object: 'internals', thorp: STARS },
  { key: 'attribution-graphs', title: 'Attribution graphs', finding: 'Tracing a production model\'s features shows it resolving intermediate facts in multi-hop questions and planning rhymes before it writes the line.', source: 'Lindsey et al. 2025', kind: 'mechanism', object: 'internals' },
  { key: 'superposition', title: 'Superposition', finding: 'Networks pack more features than they have dimensions, as nearly orthogonal directions that interfere a little.', source: 'Elhage et al. 2022', kind: 'representation', object: 'internals' },
  { key: 'sparse-autoencoders', title: 'Sparse dictionary features', finding: 'Sparse autoencoders split a model\'s activations into many interpretable features, from single tokens to abstract concepts.', source: 'Bricken et al. 2023; Templeton et al. 2024', kind: 'representation', object: 'internals' },
  { key: 'linear-representations', title: 'Concepts are directions', finding: 'Many high-level concepts are linear directions in the hidden state, readable by a probe and changeable by an edit.', source: 'Park et al. 2023', kind: 'representation', object: 'internals' },
  { key: 'truth-direction', title: 'A direction for truth', finding: 'True and false statements separate along a direction that generalises across topics.', source: 'Marks & Tegmark 2023', kind: 'representation', object: 'internals' },
  { key: 'persona-vectors', title: 'Persona vectors', finding: 'Character traits such as sycophancy or malice are directions that can be read, monitored and steered.', source: 'Chen et al. 2025', kind: 'representation', object: 'internals', thorp: { href: `${QWEN4B_PAGE}#personas`, label: "Qwen3 4B's persona vectors" } },
  { key: 'world-models', title: 'Emergent world models', finding: 'A model trained only on Othello moves holds a linearly readable map of the board.', source: 'Li et al. 2022; Nanda et al. 2023', kind: 'representation', object: 'internals' },
  { key: 'lenses', title: 'Reading the middle layers', finding: 'Decoding each layer\'s hidden state with the output head (or a learned translator) shows the prediction forming layer by layer.', source: 'nostalgebraist 2020; Belrose et al. 2023', kind: 'measurement', object: 'internals' },
  // knowledge and memory
  { key: 'ffn-memories', title: 'Feed-forward layers as memories', finding: 'Feed-forward layers act as key-value stores: keys match patterns in the input, values promote the next tokens.', source: 'Geva et al. 2021', kind: 'mechanism', object: 'knowledge' },
  { key: 'rome', title: 'Facts can be located and edited', finding: 'A factual association is stored in mid-layer feed-forward weights at the subject\'s last token, and a rank-one edit changes it.', source: 'Meng et al. 2022', kind: 'mechanism', object: 'knowledge' },
  { key: 'knowledge-capacity', title: 'Two bits a parameter', finding: 'A model stores about two bits of knowledge a parameter, and stores it extractably only when facts are seen in varied phrasings.', source: 'Allen-Zhu & Li 2024', kind: 'law', object: 'knowledge' },
  { key: 'space-time', title: 'Maps of space and time', finding: 'Models hold linear representations of where places are and when events happened.', source: 'Gurnee & Tegmark 2023', kind: 'representation', object: 'knowledge' },
  { key: 'reversal-curse', title: 'The reversal curse', finding: 'A model trained that A is B does not learn that B is A.', source: 'Berglund et al. 2023', kind: 'limit', object: 'knowledge' },
  { key: 'compositionality-gap', title: 'The compositionality gap', finding: 'Models answer each of two sub-questions more often than they answer the question that composes them, and the gap does not close with scale.', source: 'Press et al. 2022', kind: 'limit', object: 'knowledge', thorp: CHAINING },
  { key: 'two-hop-curse', title: 'The two-hop curse', finding: 'Without writing the middle step, models fail to chain two facts learned in separate documents, however well they know each.', source: 'Balesni et al. 2024', kind: 'limit', object: 'knowledge', thorp: CHAINING },
  { key: 'latent-multi-hop', title: 'The bridge entity', finding: 'When latent two-hop reasoning works, the shared middle entity is resolved in the middle layers, before the second hop.', source: 'Yang et al. 2024', kind: 'mechanism', object: 'knowledge', thorp: { href: `${DB}/stars`, label: 'the bridge, layer by layer' } },
  // evaluation
  { key: 'emergence-mirage', title: 'Emergence can be a mirage', finding: 'Many sudden jumps vanish under smooth metrics: exact-match scoring makes gradual gains look discontinuous.', source: 'Schaeffer et al. 2023', kind: 'measurement', object: 'evaluation' },
  { key: 'contamination', title: 'Benchmark contamination', finding: 'Test sets leak into training data, inflating scores in ways that are hard to detect after the fact.', source: 'Sainz et al. 2023', kind: 'measurement', object: 'evaluation' },
  { key: 'llm-judge', title: 'Models as judges', finding: 'A strong model agrees with human raters about as often as they agree with each other, with known biases toward position, length and itself.', source: 'Zheng et al. 2023', kind: 'measurement', object: 'evaluation' },
  // safety and security
  { key: 'extraction', title: 'Training data can be extracted', finding: 'Verbatim training text, including personal details, can be pulled out of a model by prompting it.', source: 'Carlini et al. 2021', kind: 'limit', object: 'safety' },
  { key: 'refusal-direction', title: 'Refusal is one direction', finding: 'Refusing harmful requests is mediated by a single direction; removing it removes the refusals.', source: 'Arditi et al. 2024', kind: 'representation', object: 'safety' },
  { key: 'many-shot', title: 'Many-shot jailbreaking', finding: 'Filling a long context with examples of compliance overrides safety training, more reliably the longer the context.', source: 'Anil et al. 2024', kind: 'limit', object: 'safety' },
  { key: 'sleeper-agents', title: 'Sleeper agents', finding: 'A backdoor trained into a model survives standard safety training, and adversarial training can teach it to hide better.', source: 'Hubinger et al. 2024', kind: 'limit', object: 'safety' },
  { key: 'alignment-faking', title: 'Alignment faking', finding: 'A model told it will be retrained can comply strategically during training to keep its preferences afterwards.', source: 'Greenblatt et al. 2024', kind: 'behaviour', object: 'safety' },
  { key: 'emergent-misalignment', title: 'Emergent misalignment', finding: 'Fine-tuning on one narrow bad behaviour (insecure code) can make a model broadly misaligned.', source: 'Betley et al. 2025', kind: 'behaviour', object: 'safety' },
];

/** A category's address segment: its name, so the crumb built from the address reads as the page does. */
export const slugOf = (c: MapCategory): string => c.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

/** An axis by its address segment, or null. */
export const axisBySlug = (slug: string | undefined): MapAxis | null => AXES.find((a) => a.slug === slug) || null;

/** The discoveries in one category of an axis. */
export const discoveriesIn = (axis: MapAxis, cat: string): FieldDiscovery[] =>
  DISCOVERIES.filter((d) => (axis.key === 'kind' ? d.kind : d.object) === cat);

/** The addresses the map adds under Demiton's discoveries, for getStaticPaths: each axis and each of its categories. */
export const FIELD_MAP_PATHS: string[] = AXES.flatMap((a) => [a.slug, ...a.categories.map((c) => `${a.slug}/${slugOf(c)}`)]);
