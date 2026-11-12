// The tests of each leaderboard category (13 November, Justin: "each category on the leaderboard needs its own
// page with all the relevant tests as cards with pros and cons of the test, and then when clicking on that test
// have the leaderboard show on that test"). One page a category (/leaderboard/<category>), one card a test; the
// card turns over to that test's board. The categories are lib/testCategories.ts's.
//
// The pros and cons are our own reading of each test, written for choosing what to trust, not a review of
// its paper: where a test's method is the publisher's and we have not read it closely, the con says what we
// can and cannot vouch for. A published test's name, description and link come from data/benchmarks.json
// (Artificial Analysis's readings); only the pros and cons are written here. Pure data, no DOM.
//
// The picks (13 November, Justin: "audit all the tests across all 8 categories and choose only the 5 best
// most widely cited and respectable"): a category keeps its own tests and carries the five most-cited respectable
// published tests beside them, ranked on how often each test's paper is cited (OpenAlex and Semantic Scholar, the
// larger), and only tests that measure the category's defining skill. A test with no paper to count (the
// Artificial Analysis indices, HMMT, AIME) cannot be ranked and is not here; nor are the next in line: LogiQA,
// ReClor, FOLIO and ZebraLogic (logic), TruthfulQA (knowledge), BigCodeBench (coding), τ²-bench and GAIA (agent).

export type BoardKind = 'logic-deck' | 'cause-deck' | 'chaining' | 'arc' | 'arcagi2' | 'ifeval' | 'face' | 'published' | 'none';

export interface CatalogTest {
  /** The ?open= address of the card on its category's page. For a published test, its benchmarks.json key. */
  key: string;
  /** Ours (a board of our own readings), published (Artificial Analysis's readings only), or an industry standard
   *  nobody has read the models we track on yet (13 November: the card says so rather than show a board). */
  source: 'ours' | 'published' | 'standard';
  /** What the back says when there is no board: why, and what would make one. */
  noBoard?: string;
  /** How often the test's paper is cited (OpenAlex / Semantic Scholar, the larger), the audit's measure of how widely it is respected. */
  cites?: number | null;
  board: BoardKind;
  /** Our tests carry their own words; a published test's come from benchmarks.json. */
  name?: string;
  tag?: string;
  about?: string;
  link?: { href: string; label: string };
  art?: string;
  pros: string[];
  cons: string[];
}

export interface CatalogCategory {
  key: string;
  about: string;
  tests: CatalogTest[];
}

/** The back of an industry-standard card (13 November): no model we track has a reading, so no board is drawn. */
const NO = 'No reading of this test is held for any model we track: Artificial Analysis does not publish it here and we have not run it, so there is no board to show and nothing is compared. Running it means fetching the dataset at a pinned revision and scoring each model the way our other tests are scored.';

const TESTS_PAGE = '/orbitals/demiton/discoveries/tests';
const STARS_PAGE = '/orbitals/demiton/discoveries/stars';

export const TEST_CATALOG: CatalogCategory[] = [
  {
    key: 'logic',
    about: 'can a model reason from what it is given: our three tests have boards, and beside them are the five most-cited industry standards for chaining and deduction, not yet read on any model we track, so their cards give the case for and against each and say so',
    tests: [
      {
        key: 'logic-deck', source: 'ours', board: 'logic-deck', art: '/art/test-chaining.png',
        name: 'The logic deck', tag: '40 items, five relations',
        about: 'Forty items across five relations — order, cause, membership, proportion and counterfactual — written with invented words and counterfactual premises, so what the model knows cannot answer them. Each is asked with both premises and with one.',
        link: { href: TESTS_PAGE, label: 'Discoveries, Tests: the logic items' },
        pros: ['Invented words and false premises, so recall cannot help: a pass is reasoning from what is stated.', 'Asked with both premises and with one, which is what gives the chaining gain: the proof a pass is chaining and not knowing.', 'Five different relations, so one trick cannot carry it.', 'Cheap enough to run on every checkpoint.'],
        cons: ['Forty items: one item is 2.5 points, so small differences are noise.', 'Written by us and not reviewed by anyone else, and no outside model published a score on it.', 'It was built to the shape of our own method, so there is a risk it measures what we taught.', 'No board of outside models exists below 1B that clears the noise.'],
      },
      {
        key: 'cause-deck', source: 'ours', board: 'cause-deck', art: '/art/test-chaining.png',
        name: 'The cause deck', tag: '96 cause items',
        about: 'Ninety-six items on cause and effect in the same invented-word style. The leaderboard holds the logic deck\'s chaining gain on its cause items — eight of them — so the board here is that reading; the full deck has no per-model board yet.',
        link: { href: TESTS_PAGE, label: 'Discoveries, Tests: the cause items' },
        pros: ['Cause and effect is a different job from membership or order, so it can fail where those pass.', 'Ninety-six items is a deck large enough to read once it is run on every model.'],
        cons: ['The board is not the deck: the leaderboard\'s reading is eight items, so a strong value counts and a small one is noise.', 'Ours, unreviewed, and with no published comparison.', 'Cause items may lean on world knowledge more than the order or membership ones do.'],
      },
      {
        key: 'chaining', source: 'ours', board: 'chaining', art: '/art/test-chaining.png',
        name: 'Chaining two facts', tag: 'the four chaining tests',
        about: 'Nature\'s breeder, the mill test, the between test and the pigeonhole test, 96 pairs in all: two premises, one conclusion neither gives alone, like the fix two bearings make on a chart. Each gives a lift and the share of pairs right.',
        link: { href: `${TESTS_PAGE}?test=chaining`, label: 'Discoveries, Tests: chaining two facts' },
        pros: ['Isolates exactly what Nothing up my sleeve is built for: combining two stated facts into a third.', 'A lift with its noise (0.03) and a chaining gain (0.05) stated, so a pass can be told from luck.', 'Four different tests, so a model must do it more than one way (a tick needs lift 0.1 and two in three right).', 'Our ships and outside models are read the same way on one board.'],
        cons: ['Ours and not peer reviewed; the competitor ladder is the only outside check.', 'Under 1B nothing chains yet, so below the small class the board is empty and the extra small page reads the steps to it instead.', 'Ninety-six pairs is a modest sample for a class with few models.', 'Not comparable with any published reasoning score.'],
      },
      {
        key: 'proofwriter', source: 'standard', cites: 570, board: 'none', noBoard: NO,
        name: 'ProofWriter', tag: 'industry standard',
        about: 'Deductive reasoning over explicit natural-language rules and facts, with the depth of the proof controlled from zero up to five steps: the question is true or false (or unknown under open-world reading) and, at depth three, it takes three chained facts to see why.',
        link: { href: 'https://arxiv.org/abs/2012.13048', label: 'ProofWriter (Tafjord et al., 2021)' },
        pros: ['The depth is a dial: a score by depth is a direct measure of how many facts a model can chain, the closest standard to what Nothing up my sleeve is for.', 'Fully synthetic, so recall cannot help and the answer is exactly checkable.', 'Large, so a reading is stable.'],
        cons: ['Templated language, so a model can learn the pattern and ace it without general reasoning.', 'Closed-world and open-world versions are easy to confuse, and scores are not comparable across them.', 'Saturated by large models, so it ranks mostly small ones.', 'Not run by us yet, and no published reading for the models we track.'],
      },
      {
        key: 'bbh', source: 'standard', cites: 2428, board: 'none', noBoard: NO,
        name: 'BIG-Bench Hard', tag: 'industry standard',
        about: 'Twenty-three of the hardest tasks in BIG-Bench, chosen because earlier models fell below the average human on them. The logic ones are logical deduction, boolean expressions, web of lies and tracking shuffled objects.',
        link: { href: 'https://arxiv.org/abs/2210.09261', label: 'BIG-Bench Hard (Suzgun et al., 2022)' },
        pros: ['The most widely reported general reasoning suite, so a number is understood everywhere.', 'Several tasks are exact algorithmic logic with a single right answer.', 'Small tasks, so a full run is cheap.'],
        cons: ['About 250 items a task, so a single task is noisy.', 'Twenty-three tasks mixed, and only a handful are logic: an overall score hides which.', 'Public since 2022 and near saturation for the frontier.', 'Not run by us yet, and no published reading for the models we track.'],
      },
      {
        key: 'musique', source: 'standard', cites: 1402, board: 'none', noBoard: NO,
        name: 'MuSiQue', tag: 'industry standard',
        about: 'Multi-hop questions of two to four hops, built by composing single-hop questions so that each hop needs the one before. It was made to close the shortcuts in earlier multi-hop sets, where a model could answer from a single paragraph.',
        link: { href: 'https://arxiv.org/abs/2108.00573', label: 'MuSiQue (Trivedi et al., 2022)' },
        pros: ['Built so that every hop is needed: harder to shortcut than HotpotQA, which a model can largely answer without the chain.', 'Two to four hops, so a score by hop count is a score for chaining.', 'Standard for multi-hop question answering, so there is a literature.'],
        cons: ['Without retrieved passages a small model\'s score mostly measures what it knows, not how it chains.', 'Scored by answer-string match (F1 and exact match), which is strict about wording.', 'Questions about real facts, so contamination is possible.', 'Not run by us yet, and no published reading for the models we track.'],
      },
      {
        key: 'babi', source: 'standard', cites: 1062, board: 'none', noBoard: NO,
        name: 'bAbI', tag: 'industry standard',
        about: 'Twenty synthetic question-answering tasks from Facebook AI Research, among them the original "two supporting facts" and "three supporting facts" tasks: a short story, and a question whose answer needs two or three of its sentences combined. The first chaining test.',
        link: { href: 'https://arxiv.org/abs/1502.05698', label: 'bAbI (Weston et al., 2015)' },
        pros: ['The oldest and cleanest chaining test: two or three supporting facts, exactly our question.', 'Synthetic and exact, with a controlled difficulty and no outside knowledge needed.', 'Tiny and instant to run.'],
        cons: ['Solved since about 2016, so a good score shows little: it is a floor, not a contest.', 'Templated stories from a small vocabulary, so a model can learn the templates.', 'Not run by us yet, and no published reading for the models we track.'],
      },
      {
        key: "hotpotqa", source: 'standard', board: 'none', noBoard: NO, cites: 6099,
        name: "HotpotQA", tag: 'industry standard',
        about: "About 113,000 questions built from Wikipedia that need two paragraphs to answer, with the supporting sentences marked: the best-known multi-hop reading test, and the closest large standard to chaining two facts.",
        link: { href: "https://arxiv.org/abs/1809.09600", label: "HotpotQA (Yang et al., 2018)" },
        pros: ["The supporting facts are labelled, so a model’s chaining can be checked and not just its answer.", "The most cited multi-hop test, with a large literature to compare against.", "Large enough that a reading is stable."],
        cons: ["Many of its questions can be answered from one paragraph, so a good score does not prove two hops (MuSiQue was built to close that gap).", "Scored by answer-string match, which is strict about wording.", "Real-world Wikipedia facts, so what a model already knows mixes into the score.", "Not run by us yet, and no published reading for the models we track."],
      },
    ],
  },
  {
    key: 'knowledge',
    about: 'what a model holds: grade-school science read by loss, beside the five most-cited tests of knowledge and factual recall, none yet read on a model we track',
    tests: [
      {
        key: 'arc', source: 'ours', board: 'arc', art: '/art/test-arc.png',
        name: 'AI2 ARC', tag: 'Easy 2,376 · Challenge 1,172',
        about: 'Grade-school science, four answers a question. Read zero-shot with the option\'s own text as the continuation, the lowest mean loss the bet: no letters, no examples, no generation.',
        link: { href: 'https://allenai.org/data/arc', label: 'AI2 Reasoning Challenge (Clark et al., 2018)' },
        pros: ['Peer-recognised, and large enough (2,376 and 1,172) to read small differences.', 'Has a gradient under 1B, where most tests are flat: Easy ranks a class that nothing else can.', 'Zero-shot and loss-scored, so our ships and outside models are read identically.'],
        cons: ['Grade-school questions a pretraining corpus may well hold: contamination is not ruled out.', 'Challenge sits at or under chance for every model trained before 2025, so it ranks nothing at small sizes.', 'Not comparable with published ARC numbers, which are 25-shot and scored on the letter.', 'Saturates for large models, so it says little above the small class.'],
      },
      {
        key: "mmlu", source: 'standard', board: 'none', noBoard: NO, cites: 5330,
        name: "MMLU", tag: 'industry standard',
        about: "Multiple-choice questions across 57 subjects, from elementary maths to law and medicine: the most widely reported test of what a language model knows.",
        link: { href: "https://arxiv.org/abs/2009.03300", label: "Measuring Massive Multitask Language Understanding (Hendrycks et al., 2021)" },
        pros: ["The test everyone quotes, so a number is understood anywhere.", "Fifty-seven subjects, so it covers breadth where AI2 ARC covers one level.", "Automatically scored and cheap to run."],
        cons: ["Near saturation for the frontier, so it separates only the smaller models.", "Some questions are mislabelled or ambiguous, and it has been public for years, so contamination is likely.", "Four options, so chance is 25%, and scores move with the prompt format.", "Not run by us yet, and no published reading for the models we track."],
      },
      {
        key: "triviaqa", source: 'standard', board: 'none', noBoard: NO, cites: 3050,
        name: "TriviaQA", tag: 'industry standard',
        about: "About 95,000 trivia questions written by trivia enthusiasts, each with evidence documents: open-ended recall of long-tail facts, with no options to choose between.",
        link: { href: "https://arxiv.org/abs/1705.03551", label: "TriviaQA (Joshi et al., 2017)" },
        pros: ["Open-ended answers, so it tests recall rather than recognition.", "Long-tail facts that multiple choice does not reach.", "Widely used for closed-book question answering."],
        cons: ["Scoring by string match is brittle: a right answer in other words can be marked wrong.", "Web and Wikipedia text are in most training sets, so some of it is remembered, not known.", "Small models score low and look alike.", "Not run by us yet, and no published reading for the models we track."],
      },
      {
        key: "natural-questions", source: 'standard', board: 'none', noBoard: NO, cites: 2479,
        name: "Natural Questions", tag: 'industry standard',
        about: "Real, anonymised queries that people typed into Google, paired with Wikipedia pages and annotated answers: the questions nobody wrote to be hard.",
        link: { href: "https://aclanthology.org/Q19-1026/", label: "Natural Questions (Kwiatkowski et al., 2019)" },
        pros: ["Real user questions, not written by annotators for a benchmark.", "Annotated long and short answers from Wikipedia.", "A standard for open-domain question answering."],
        cons: ["Built for reading a page; closed-book use is a different test and its scores are not comparable with the original.", "Some questions are ambiguous or time-bound.", "String-match scoring, as TriviaQA.", "Not run by us yet, and no published reading for the models we track."],
      },
      {
        key: "mmlu-pro", source: 'standard', board: 'none', noBoard: NO, cites: 1130,
        name: "MMLU-Pro", tag: 'industry standard',
        about: "A harder MMLU: ten options a question instead of four, the trivial questions removed and more of the rest needing reasoning, so chance is 10% and the top of the field is not crowded.",
        link: { href: "https://arxiv.org/abs/2406.01574", label: "MMLU-Pro (Wang et al., 2024)" },
        pros: ["Ten options, so guessing is worth much less.", "Less saturated than MMLU, so it still separates strong models.", "Less sensitive to the wording of the prompt, its authors report."],
        cons: ["Newer, so fewer readings and a smaller literature.", "Drawn largely from MMLU’s own pool, so the contamination worry carries over.", "Leans on step-by-step answers, so a model that does not reason aloud is held back.", "Not run by us yet, and no published reading for the models we track."],
      },
      {
        key: "simpleqa", source: 'standard', board: 'none', noBoard: NO, cites: 532,
        name: "SimpleQA", tag: 'industry standard',
        about: "About four thousand short fact-seeking questions, each with one indisputable answer, marked correct, incorrect or not attempted: a test of whether a model knows a fact or invents one.",
        link: { href: "https://arxiv.org/abs/2411.04368", label: "Measuring short-form factuality in large language models (Wei et al., 2024)" },
        pros: ["One verifiable answer a question, so grading is not an argument.", "‘Not attempted’ is a legal answer, so it rewards a model that knows what it does not know.", "Built to be hard for current models, so it is not saturated."],
        cons: ["The questions were picked against GPT-4, so the set is tilted towards what that model gets wrong.", "A judge model grades the answers, with the usual bias.", "Narrow short facts only, and small models score close to zero.", "Not run by us yet, and no published reading for the models we track."],
      },
    ],
  },
  {
    key: 'reasoning',
    about: 'fluid reasoning and hard problems: ARC-AGI-2 is our reading (a pilot), and the five most-cited tests sit beside it; Artificial Analysis has readings for GPQA Diamond and HLE',
    tests: [
      {
        key: 'arcagi2', source: 'ours', board: 'arcagi2', art: '/art/test-arcagi2.png',
        name: 'ARC-AGI-2', tag: 'pass@2 · 120 tasks',
        about: 'The canonical intelligence ranking: pass@2 on the 120-task evaluation set, grid puzzles with no language or domain knowledge to memorise. Published scores are the public leaderboard\'s; our reading is the Kipling ARC arm\'s, and it is a pilot.',
        link: { href: 'https://arcprize.org/arc-agi', label: 'ARC Prize: ARC-AGI-2' },
        pros: ['Built to resist memorisation: each task is new, with no language or domain knowledge to lean on.', 'The best-known measure of fluid reasoning, so a number means something outside this project.', 'A fixed 120-task set and pass@2, so scores are comparable between readings.'],
        cons: ['Scores are near zero for any small model prompted cold, so it does not separate models under about 4B.', 'Our readings are pilots on fewer tasks, and a pilot is never compared with a published score.', 'Two different contests under one name: prompted cold, or trained on the ARC tasks first.', 'Grids written as text are a hard format for a small model before reasoning even starts.'],
      },
      { key: 'gpqa-diamond', source: 'published', cites: 1690, board: 'published',
        pros: ['Graduate-level science questions written to resist search, so a score is not just retrieval.', 'A broad reasoning floor that is widely reported.'],
        cons: ['About two hundred questions, so a few points are noise.', 'Multiple choice, so chance is not zero and prompting matters.', 'Near saturation for the frontier and possibly contaminated for newer models.', 'Published only, and it is not a coding or config test.'] },
      { key: 'hle', source: 'published', cites: 1018, board: 'published',
        pros: ['The hardest closed-book questions in the field, so it does not saturate.', 'Wide subject coverage written by experts.'],
        cons: ['Every model we track is near the floor, so it separates nothing at these sizes.', 'Some questions have been disputed, so the ceiling is not a clean 100.', 'Published only, no tools, and no use for deciding what to build on.'] },
      {
        key: "gsm8k", source: 'standard', board: 'none', noBoard: NO, cites: 12126,
        name: "GSM8K", tag: 'industry standard',
        about: "About 8,500 grade-school maths word problems that take two to eight steps, each with one numeric answer: the standard test of multi-step arithmetic reasoning.",
        link: { href: "https://arxiv.org/abs/2110.14168", label: "Training Verifiers to Solve Math Word Problems (Cobbe et al., 2021)" },
        pros: ["Simple, exact numeric answers, so it is easy to grade.", "Quoted on almost every model report, so a number has company.", "Multi-step but not hard, so it reads small models too."],
        cons: ["Saturated for the frontier, so it says little above the small and medium classes.", "Public since 2021, so contamination is likely.", "Needs the model to reason aloud; read bare, small models score close to zero.", "Not run by us yet, and no published reading for the models we track."],
      },
      {
        key: "math", source: 'standard', board: 'none', noBoard: NO, cites: 3883,
        name: "MATH", tag: 'industry standard',
        about: "Twelve and a half thousand competition problems from contests such as the AMC and AIME, each with a step-by-step solution and an exact answer, in five levels of difficulty.",
        link: { href: "https://arxiv.org/abs/2103.03874", label: "Measuring Mathematical Problem Solving With the MATH Dataset (Hendrycks et al., 2021)" },
        pros: ["Harder than GSM8K, with graded levels, so it keeps separating models longer.", "Exact answers, so it is graded by program.", "Widely reported, usually as the 500-problem subset."],
        cons: ["Contamination and saturation are real for the largest models.", "Answer-format matching can mark a right answer wrong.", "Small models sit near zero without reasoning aloud.", "Not run by us yet, and no published reading for the models we track."],
      },
      {
        key: "arc-agi-1", source: 'standard', board: 'none', noBoard: NO, cites: 1364,
        name: "ARC-AGI-1", tag: 'industry standard',
        about: "The original Abstraction and Reasoning Corpus from Chollet’s On the Measure of Intelligence: 800 grid puzzles that test learning a new rule from a few examples, with no knowledge to lean on.",
        link: { href: "https://arxiv.org/abs/1911.01547", label: "On the Measure of Intelligence (Chollet, 2019)" },
        pros: ["Built to resist memorisation: every task is a new rule.", "A famous, long-lived measure of fluid reasoning.", "Our own ARC-AGI-2 reading follows the same format, so the two are comparable in kind."],
        cons: ["Largely overtaken by ARC-AGI-2: the top systems now score high on it, with a great deal of compute.", "The public tasks are in training data, so some scores are not clean.", "Grids written as text are a hard format for a small model.", "Not run by us yet, and no published reading for the models we track."],
      },
    ],
  },
  {
    key: 'instruction',
    about: 'whether a model does what it is told: IFEval is ours, and the five most-cited tests sit beside it, from graded constraints to judged conversations; Artificial Analysis has readings for IFBench and Multi-IF',
    tests: [
      {
        key: 'ifeval', source: 'ours', board: 'ifeval', art: '/art/test-ifeval.png',
        name: 'IFEval', tag: '541 prompts',
        about: 'Five hundred and forty-one prompts, each with orders a program can check — no commas, three paragraphs, end with this phrase — read by the authors\' 25 verifiers. Prompt-level strict: every order in the prompt followed, or the prompt fails.',
        link: { href: 'https://arxiv.org/abs/2311.07911', label: 'Instruction-Following Evaluation (Zhou et al., 2023)' },
        pros: ['Programmatic checks and no judge: a score cannot be argued with.', 'Peer-recognised and cheap to run, so every checkpoint gets a reading.', 'Prompt-level strict is a hard bar: one missed order fails the prompt.'],
        cons: ['The constraints are easy and artificial, and the frontier is close to saturation.', 'Can be rigged: a model trained on the 541 prompts learns the checks, not instruction following (we mark those rows and never quote them bare).', 'Our reading is greedy with a 512-piece cap and a base model gets the prompt bare, so it is not comparable with published chat-template numbers.'],
      },
      { key: 'ifbench', source: 'published', cites: 160, board: 'published',
        pros: ['Hundreds of new, out-of-distribution constraints, so it is less likely to have been trained on than IFEval.', 'Verifiable by program rather than by a judge.'],
        cons: ['Published only, so we cannot rerun it.', 'The constraints are still artificial: following them exactly is not the same as following a house convention.', 'Only the medium class has a reading here.'] },
      { key: 'multi-if', source: 'published', cites: 146, board: 'published',
        pros: ['Instruction following across several turns and several languages: whether turn one\'s orders still hold at turn five.', 'Catches drift that a one-prompt test cannot.'],
        cons: ['Errors compound over turns, so a score mixes instruction following with memory.', 'The language mix means a low score may be a language gap, not an obedience gap.', 'Published only.'] },
      {
        key: "mt-bench", source: 'standard', board: 'none', noBoard: NO, cites: 5250,
        name: "MT-Bench", tag: 'industry standard',
        about: "Eighty two-turn questions across eight kinds of task, scored from 1 to 10 by a strong judge model: the test that made model-as-judge a standard way to grade a chat model.",
        link: { href: "https://arxiv.org/abs/2306.05685", label: "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena (Zheng et al., 2023)" },
        pros: ["Tests following instructions across a conversation, not one prompt.", "Cheap to run, and its judge agrees with human raters about as often as they agree with each other, its authors found.", "The most cited test in the category."],
        cons: ["Eighty questions, so differences of a few tenths are noise.", "The judge has known biases toward position, length and its own answers.", "Near saturation for strong models.", "Not run by us yet, and no published reading for the models we track."],
      },
      {
        key: "arena-hard", source: 'standard', board: 'none', noBoard: NO, cites: 499,
        name: "Arena-Hard", tag: 'industry standard',
        about: "Five hundred hard prompts picked from the Chatbot Arena’s real conversations, graded by a judge model against a reference: built to separate strong models and to track the Arena’s human vote.",
        link: { href: "https://arxiv.org/abs/2406.11939", label: "From Crowdsourced Data to High-Quality Benchmarks: Arena-Hard (Li et al., 2024)" },
        pros: ["Real prompts from real users, and hard ones.", "Separates models better than MT-Bench, its authors report, and agrees with the Arena’s ranking.", "Refreshable, so it can stay ahead of contamination."],
        cons: ["Judge-graded, with a bias toward longer, more stylish answers (a length control was added to answer it).", "Mostly one-turn, so it says less about obeying standing orders.", "Not run by us yet, and no published reading for the models we track."],
      },
      {
        key: "infobench", source: 'standard', board: 'none', noBoard: NO, cites: 198,
        name: "InFoBench", tag: 'industry standard',
        about: "Five hundred instructions, each broken into simple yes-or-no requirements (2,250 in all), so a model is scored on the share of an instruction it followed, not on all or nothing.",
        link: { href: "https://arxiv.org/abs/2401.03601", label: "InFoBench (Qin et al., 2024)" },
        pros: ["Measures partial following, which a strict pass or fail hides.", "Every requirement is a plain question, so it is easy to inspect where a model slipped.", "Covers constraints that no program can check."],
        cons: ["The yes-or-no checks are answered by a judge model, so it carries a judge’s bias.", "Small, and far less widely adopted than IFEval.", "Not run by us yet, and no published reading for the models we track."],
      },
    ],
  },
  {
    key: 'coding',
    about: 'writing code that runs: we measure no coding test yet, so the five most-cited tests stand alone and none has been read on a model we track',
    tests: [
      {
        key: "humaneval", source: 'standard', board: 'none', noBoard: NO, cites: 12109,
        name: "HumanEval", tag: 'industry standard',
        about: "A hundred and sixty-four hand-written Python programming problems, each with unit tests, scored as the chance that a sample passes (pass@k): the test that set the standard for judging a code model.",
        link: { href: "https://arxiv.org/abs/2107.03374", label: "Evaluating Large Language Models Trained on Code (Chen et al., 2021)" },
        pros: ["The most cited and most reported coding test.", "Unit tests decide, so there is no judge.", "Small, so a reading is cheap."],
        cons: ["Only 164 problems, so differences of a few points are noise.", "Saturated for the frontier, and public since 2021, so contamination is likely.", "Short, function-level tasks, nothing like editing a real codebase.", "Its tests are weak enough to pass wrong code (EvalPlus adds more).", "Not run by us yet, and no published reading for the models we track."],
      },
      {
        key: "mbpp", source: 'standard', board: 'none', noBoard: NO, cites: 4784,
        name: "MBPP", tag: 'industry standard',
        about: "About a thousand entry-level Python problems written by crowd workers, each with three tests: the second standard code test beside HumanEval.",
        link: { href: "https://arxiv.org/abs/2108.07732", label: "Program Synthesis with Large Language Models (Austin et al., 2021)" },
        pros: ["More problems than HumanEval, so a reading is steadier.", "Simple and cheap, and widely reported.", "Test-graded, with no judge."],
        cons: ["Entry-level only, and some problems are ambiguous or have flawed tests.", "Saturated and public, so contamination is likely.", "Not run by us yet, and no published reading for the models we track."],
      },
      {
        key: "swe-bench", source: 'standard', board: 'none', noBoard: NO, cites: 2081,
        name: "SWE-bench", tag: 'industry standard',
        about: "Real GitHub issues from twelve Python projects (2,294 of them; 500 in the human-checked Verified set), where the model must write a patch that makes the project’s own tests pass: the test closest to real software work.",
        link: { href: "https://arxiv.org/abs/2310.06770", label: "SWE-bench (Jimenez et al., 2024)" },
        pros: ["Real issues in real repositories, graded by the project’s own tests.", "The nearest published test to editing an existing file, which is our work.", "The Verified subset removes unclear tasks."],
        cons: ["Needs an agent harness around the model, and a score depends heavily on that harness.", "Expensive to run, and small models score close to zero.", "Python only, from a handful of popular projects, which may be in training data.", "Not run by us yet, and no published reading for the models we track."],
      },
      {
        key: "livecodebench", source: 'standard', board: 'none', noBoard: NO, cites: 1522,
        name: "LiveCodeBench", tag: 'industry standard',
        about: "Problems collected continuously from LeetCode, AtCoder and Codeforces and stamped with their release date, so a model can be scored only on problems newer than its training; it also tests repair, execution and test prediction.",
        link: { href: "https://arxiv.org/abs/2403.07974", label: "LiveCodeBench (Jain et al., 2024)" },
        pros: ["Dated problems, so contamination can be avoided by choosing the window.", "Reads more than writing: self-repair, code execution and test-output prediction.", "Test-graded."],
        cons: ["A moving target: scores on different releases are not comparable.", "Competitive-programming problems, which are not everyday code.", "Heavy test suites make it slower to run.", "Not run by us yet, and no published reading for the models we track."],
      },
      {
        key: "evalplus", source: 'standard', board: 'none', noBoard: NO, cites: 902,
        name: "EvalPlus (HumanEval+)", tag: 'industry standard',
        about: "HumanEval and MBPP with many times more tests each, written to catch code that passes the original weak ones: the same problems, graded harder.",
        link: { href: "https://arxiv.org/abs/2305.01210", label: "Is Your Code Generated by ChatGPT Really Correct? (Liu et al., 2023)" },
        pros: ["Catches wrong code that slips past HumanEval’s few tests.", "The same problems, so scores line up with the originals.", "Test-graded, with no judge."],
        cons: ["The same few problems, so it inherits HumanEval’s size and contamination.", "Function-level only.", "Not run by us yet, and no published reading for the models we track."],
      },
    ],
  },
  {
    key: 'agent',
    about: 'acting through tools until the errand is done: our drone tasks run browser, email and phone work but are not scored yet, and the five most-cited agent tests stand beside them, none read on a model we track',
    tests: [
      {
        key: 'drones', source: 'ours', board: 'none', noBoard: 'Not a benchmark yet: no task set is fixed and nothing scores a run, so there is no board. A fixed set of tasks with a pass or fail grade would make one.',
        name: 'Our drone tasks', tag: 'browser · email · phone, unscored',
        about: 'Our own drones run browser, email and phone tasks for real. They are not yet a scored benchmark: nothing grades a run pass or fail, so there is no board to show.',
        link: { href: '/orbitals/demiton', label: 'Demiton' },
        pros: ['The closest thing to the work we actually want an agent to do: real browsers, real mail, a real phone.', 'Ours, so we can make the tasks as hard and as particular as the work is.'],
        cons: ['Not a benchmark yet: no task set is fixed and nothing scores a run.', 'No outside model has been run on them, so there is nothing to compare.', 'Real services change under us, so a task may not repeat.'],
      },
      {
        key: "webarena", source: 'standard', board: 'none', noBoard: NO, cites: 1435,
        name: "WebArena", tag: 'industry standard',
        about: "Eight hundred and twelve long tasks on self-hosted websites (a shop, a forum, a code host, a content system), scored by whether the final state is right: the standard test of a web agent.",
        link: { href: "https://arxiv.org/abs/2307.13854", label: "WebArena (Zhou et al., 2024)" },
        pros: ["Realistic sites, and the outcome is checked by program, not by opinion.", "Self-hosted, so runs are repeatable.", "The most cited agent environment."],
        cons: ["Heavy to set up, and scores depend on the agent harness around the model.", "Fixed sites that models may have seen, and some tasks are flaky.", "Small models score close to zero.", "Not run by us yet, and no published reading for the models we track."],
      },
      {
        key: "agentbench", source: 'standard', board: 'none', noBoard: NO, cites: 1421,
        name: "AgentBench", tag: 'industry standard',
        about: "Eight environments, among them an operating system, a database, a knowledge graph, a card game, web shopping and web browsing, scoring a model as an agent across all of them.",
        link: { href: "https://arxiv.org/abs/2308.03688", label: "AgentBench (Liu et al., 2024)" },
        pros: ["Broad: eight different environments in one suite.", "An early standard, so there is plenty to compare.", "Each environment is graded by program."],
        cons: ["An aggregate hides which environment a model fails in.", "Harness-dependent, and older than the newer suites.", "Several environments are toy-like beside real work.", "Not run by us yet, and no published reading for the models we track."],
      },
      {
        key: "tau-bench", source: 'standard', board: 'none', noBoard: NO, cites: 1198,
        name: "τ-bench", tag: 'industry standard',
        about: "A simulated user and a set of tools in retail and airline settings, with a written policy the agent must follow; scored by whether the database ends up right and, with pass^k, by whether it does so every time.",
        link: { href: "https://arxiv.org/abs/2406.12045", label: "τ-bench (Yao et al., 2024)" },
        pros: ["Tests following rules while acting, not just using tools.", "pass^k scores reliability: succeeding once is not the same as succeeding every time.", "Graded by the final database, not by a judge."],
        cons: ["The simulated user is itself a model, so runs vary.", "Two narrow domains, and costly to run.", "τ²-bench has since extended it.", "Not run by us yet, and no published reading for the models we track."],
      },
      {
        key: "browsecomp", source: 'standard', board: 'none', noBoard: NO, cites: 700,
        name: "BrowseComp", tag: 'industry standard',
        about: "About 1,266 hard questions whose answers are short and checkable but take persistent browsing to find: easy to verify, hard to solve.",
        link: { href: "https://arxiv.org/abs/2504.12516", label: "BrowseComp (Wei et al., 2025)" },
        pros: ["Short answers that are easy to grade.", "Tests persistence, not just a single lookup.", "Not saturated."],
        cons: ["Needs a browsing tool, so it grades the agent as a whole and not the model.", "A narrow skill, and small models score close to zero.", "Made by one lab, with answers that can leak.", "Not run by us yet, and no published reading for the models we track."],
      },
      {
        key: "osworld", source: 'standard', board: 'none', noBoard: NO, cites: 682,
        name: "OSWorld", tag: 'industry standard',
        about: "Three hundred and sixty-nine tasks across real operating systems (Ubuntu, Windows, macOS) and real applications, scored by checking the machine’s state afterwards: the standard test of a computer-use agent.",
        link: { href: "https://arxiv.org/abs/2404.07972", label: "OSWorld (Xie et al., 2024)" },
        pros: ["Real applications and real screens, checked by execution.", "The nearest published test to our browser, email and phone drones.", "Multimodal."],
        cons: ["Heavy virtual machines to run, and slow.", "Scores have been low and depend on the harness.", "Needs a model that can read screens, which rules out the small ones.", "Not run by us yet, and no published reading for the models we track."],
      },
    ],
  },
  {
    key: 'long-context',
    about: 'finding and combining facts across a long context: we measure none yet, so the five most-cited tests stand alone and none has been read on a model we track',
    tests: [
      {
        key: "longbench", source: 'standard', board: 'none', noBoard: NO, cites: 1145,
        name: "LongBench", tag: 'industry standard',
        about: "A bilingual set of long-context tasks across question answering, summarisation, few-shot learning, code and synthetic retrieval: the first widely used multi-task long-context test.",
        link: { href: "https://arxiv.org/abs/2308.14508", label: "LongBench (Bai et al., 2024)" },
        pros: ["Realistic tasks, not only needles in haystacks.", "Several task types in one suite, so a single trick cannot carry it.", "The most cited test in the category."],
        cons: ["Its inputs are now short beside modern context windows.", "Some tasks are scored by overlap with a reference, which is crude.", "Public, so contamination is possible.", "Not run by us yet, and no published reading for the models we track."],
      },
      {
        key: "ruler", source: 'standard', board: 'none', noBoard: NO, cites: 1088,
        name: "RULER", tag: 'industry standard',
        about: "Synthetic long-context tasks beyond the simple needle: several needles, tracing a variable through the text, aggregating, and question answering, at any length you set, to find a model’s effective context.",
        link: { href: "https://arxiv.org/abs/2404.06654", label: "RULER (Hsieh et al., 2024)" },
        pros: ["Length is a dial, so it shows where a model’s claimed context stops being usable.", "Exactly scored.", "Harder than the plain needle test, which most models now pass."],
        cons: ["Synthetic, so it may not predict real long-document work.", "Costly at the longest lengths.", "Not run by us yet, and no published reading for the models we track."],
      },
      {
        key: "longbench-v2", source: 'standard', board: 'none', noBoard: NO, cites: 333,
        name: "LongBench v2", tag: 'industry standard',
        about: "Five hundred and three hard multiple-choice questions over documents of eight thousand to two million words, which human experts needed more than fifteen minutes to answer.",
        link: { href: "https://arxiv.org/abs/2412.15204", label: "LongBench v2 (Bai et al., 2025)" },
        pros: ["Hard and realistic, and graded automatically because it is multiple choice.", "Covers very long inputs, up to millions of words.", "Newer, so less likely to be in training data."],
        cons: ["Four options, so chance is 25%.", "Only 503 questions, and very expensive to run at full length.", "Needs a model with a long context, so small ones cannot be read.", "Not run by us yet, and no published reading for the models we track."],
      },
      {
        key: "infinitebench", source: 'standard', board: 'none', noBoard: NO, cites: 211,
        name: "∞Bench", tag: 'industry standard',
        about: "Tasks over inputs beyond 100,000 tokens, averaging about 200,000: retrieval, question answering, summarisation, maths, code and dialogue, the first standard for contexts that long.",
        link: { href: "https://arxiv.org/abs/2402.13718", label: "∞Bench (Zhang et al., 2024)" },
        pros: ["The first test built for contexts past a hundred thousand tokens.", "A mix of synthetic and realistic tasks.", "Several tasks are exactly scored."],
        cons: ["Needs a very long context, and is costly.", "Less used now that newer suites exist.", "Some tasks are synthetic.", "Not run by us yet, and no published reading for the models we track."],
      },
      {
        key: "l-eval", source: 'standard', board: 'none', noBoard: NO, cites: 193,
        name: "L-Eval", tag: 'industry standard',
        about: "Twenty long-input tasks over several hundred documents of three thousand to two hundred thousand tokens, with human-written instructions and answers, and a study of which metrics can be trusted.",
        link: { href: "https://arxiv.org/abs/2307.11088", label: "L-Eval (An et al., 2024)" },
        pros: ["Human-written instructions and references.", "Looks hard at which metrics can be trusted for long outputs.", "Several kinds of task."],
        cons: ["Smaller and older than the other long-context suites.", "Some tasks still rely on overlap scores.", "Not run by us yet, and no published reading for the models we track."],
      },
    ],
  },
  {
    key: 'abilities',
    about: 'the four Faces: abilities a ship earns when its own measure passes a mark, not tests of a task; each card is one Face, beside Qwen 3 4B the reference chainer',
    tests: [
      {
        key: 'nevermore', source: 'ours', board: 'face', art: '/art/test-faces.png',
        name: 'The Nevermore', tag: 'copy gain · mark 1.0',
        about: 'Does the model predict a repeated passage better the second time? The copy gain is how much lower its loss is on the repeat than on the first reading: in-context copying, the core of how a ship uses what it has just been shown.',
        link: { href: STARS_PAGE, label: 'Discoveries, Stars: the four Faces' },
        pros: ['A direct, cheap measure of in-context copying, the ability chaining leans on.', 'Same procedure for every class, so it is a clean ladder.', 'The mark is stated, and a Face is earned by passing it, not pinned.'],
        cons: ['An internal property, not a task: passing it does not mean the model can do anything useful.', 'Ours alone, with one outside reference (Qwen 3 4B), so it has no published peer.', 'A class\'s cell is its best ship\'s, so it is a ceiling, not an average.'],
      },
      {
        key: 'counter', source: 'ours', board: 'face', art: '/art/test-faces.png',
        name: 'The Counter', tag: 'sentence-position R² · mark 0.5',
        about: 'Can the model tell how far into a sentence it is? The R² of a read-out of sentence position from its hidden state: a model that counts has somewhere to hold a count.',
        link: { href: STARS_PAGE, label: 'Discoveries, Stars: the four Faces' },
        pros: ['Measures whether position is represented at all, which counting and ordering need.', 'Read from the model\'s insides, so it does not depend on prompting.'],
        cons: ['A probing result: a model can encode position without using it.', 'Abstract, so a pass says little about what the model will do.', 'Ours alone, with one outside reference.'],
      },
      {
        key: 'scales', source: 'ours', board: 'face', art: '/art/test-faces.png',
        name: 'The Scales', tag: 'order gain · mark 0.1',
        about: 'Can the model order things? The order gain is the model\'s lift on the logic deck\'s order items: whether it holds which comes before which.',
        link: { href: STARS_PAGE, label: 'Discoveries, Stars: the four Faces' },
        pros: ['A task-shaped reading, taken from the logic deck, so it is closer to behaviour than a probe.', 'The mark is stated, and a Face is earned by passing it, not pinned.'],
        cons: ['Rests on the logic deck\'s order items: few of them, so it is noisy.', 'Ours alone, and the decks were written to our own method.', 'A small lift and noise are close together, so a pass is thin.'],
      },
      {
        key: 'mover', source: 'ours', board: 'face', art: '/art/test-faces.png',
        name: 'The Mover', tag: 'one-hop lift · mark 0.1',
        about: 'Can the model follow one stated premise? The one-hop lift is how much better it does when the premise is given than when it is not: the step before chaining two.',
        link: { href: STARS_PAGE, label: 'Discoveries, Stars: the four Faces' },
        pros: ['The step on the way to chaining, so it is the Face that predicts the headline result.', 'Read by its one-hop ability, not by what the model looks like inside.'],
        cons: ['Passing one hop is not chaining: the chaining gain is the proof, and this is only the step before.', 'Ours alone, on the logic deck\'s items.', 'The mark is low and noise is close to it, so a class may flicker across it.'],
      },
    ],
  },
];

export const catalogOf = (key: string): CatalogCategory | null => TEST_CATALOG.find((c) => c.key === key) || null;
