// The tests of each leaderboard category (13 November, Justin: "each category on the leaderboard needs its own
// page with all the relevant tests as cards with pros and cons of the test, and then when clicking on that test
// have the leaderboard show on that test"). One page a category (/leaderboard/<category>), one card a test; the
// card turns over to that test's board. The categories are lib/testCategories.ts's.
//
// The pros and cons are our own reading of each test, written for choosing what to trust, not a review of
// its paper: where a test's method is the publisher's and we have not read it closely, the con says what we
// can and cannot vouch for. A published test's name, description and link come from data/benchmarks.json
// (Artificial Analysis's readings); only the pros and cons are written here. Pure data, no DOM.

export type BoardKind = 'logic-deck' | 'cause-deck' | 'chaining' | 'arc' | 'arcagi2' | 'ifeval' | 'face' | 'published' | 'none';

export interface CatalogTest {
  /** The ?open= address of the card on its category's page. For a published test, its benchmarks.json key. */
  key: string;
  /** Ours (a board of our own readings), published (Artificial Analysis's readings only), or an industry standard
   *  nobody has read the models we track on yet (13 November: the card says so rather than show a board). */
  source: 'ours' | 'published' | 'standard';
  /** What the back says when there is no board: why, and what would make one. */
  noBoard?: string;
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
const NO = 'No reading of this test is held for any model we track: Artificial Analysis does not publish it and we have not run it. It is on the list to run, as a multiple-choice or short-answer test like our others; until then there is no board to show and nothing here is compared.';

const TESTS_PAGE = '/orbitals/demiton/discoveries/tests';
const STARS_PAGE = '/orbitals/demiton/discoveries/stars';

export const TEST_CATALOG: CatalogCategory[] = [
  {
    key: 'logic',
    about: 'can a model reason from what it is given: the three tests of ours have boards; the eight industry standards beside them (13 November, Justin: "surely we\'re missing the top industry standards") are not read on any model we track yet, so their cards give the case for and against each and say so',
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
        key: 'logiqa', source: 'standard', board: 'none', noBoard: NO,
        name: 'LogiQA 2.0', tag: 'industry standard · not yet read',
        about: 'Logical reading comprehension: multiple-choice questions written for civil-service exams, each a passage, a question and four options that need a logical step to choose between. LogiQA 2.0 is the cleaned and extended edition, in English and Chinese.',
        link: { href: 'https://github.com/csitfun/LogiQA2.0', label: 'LogiQA 2.0 (csitfun)' },
        pros: ['Questions written by people for people, so they test everyday logic on realistic text.', 'Widely reported in logical-reasoning surveys, so a number would mean something outside this project.', 'Multiple choice and automatically scored, so it is cheap and exact to run.'],
        cons: ['Four options, so chance is 25% and small models sit close to it.', 'A mix of reading comprehension and logic: a miss may be a reading failure.', 'Exam questions and public for years, so contamination is likely for models trained on the web.', 'Not run by us yet, and no published reading for the models we track.'],
      },
      {
        key: 'reclor', source: 'standard', board: 'none', noBoard: NO,
        name: 'ReClor', tag: 'industry standard · not yet read',
        about: 'Logical reasoning from the reading-comprehension sections of standardised graduate admission tests: a passage, a question and four options. Its test set is split into an EASY half that a biased model can answer without the passage and a HARD half that it cannot.',
        link: { href: 'https://arxiv.org/abs/2002.04326', label: 'ReClor (Yu et al., 2020)' },
        pros: ['Harder than most reading comprehension: the questions ask what follows, what is assumed or what weakens an argument.', 'The EASY and HARD split exposes a model that exploits answer biases instead of reasoning.', 'Standard in logical-reasoning papers, so there is a literature to compare against.'],
        cons: ['Four options, so chance is 25%.', 'Exam-style passages that a web-trained model may have seen.', 'Rewards test-taking habits as well as logic.', 'Not run by us yet, and no published reading for the models we track.'],
      },
      {
        key: 'folio', source: 'standard', board: 'none', noBoard: NO,
        name: 'FOLIO', tag: 'industry standard · not yet read',
        about: 'Natural-language reasoning with first-order logic: expert-written stories whose conclusion is true, false or unknown, each paired with a logic formula so the label is checked rather than opined.',
        link: { href: 'https://arxiv.org/abs/2209.00840', label: 'FOLIO (Han et al., 2022)' },
        pros: ['Labels are checked against first-order logic, so the answer is not a matter of taste.', 'Expert-written, with real vocabulary and varied structure, unlike templated rule sets.', '"Unknown" is a legal answer, which punishes a model that always guesses a side.'],
        cons: ['A modest size (a thousand or so stories), so small differences are noise.', 'Three labels, so chance is a third and a biased model can look better than it is.', 'Real-world content lets a model lean on what it knows over the stated premises.', 'Not run by us yet, and no published reading for the models we track.'],
      },
      {
        key: 'proofwriter', source: 'standard', board: 'none', noBoard: NO,
        name: 'ProofWriter', tag: 'industry standard · not yet read',
        about: 'Deductive reasoning over explicit natural-language rules and facts, with the depth of the proof controlled from zero up to five steps: the question is true or false (or unknown under open-world reading) and, at depth three, it takes three chained facts to see why.',
        link: { href: 'https://arxiv.org/abs/2012.13048', label: 'ProofWriter (Tafjord et al., 2021)' },
        pros: ['The depth is a dial: a score by depth is a direct measure of how many facts a model can chain, the closest standard to what Nothing up my sleeve is for.', 'Fully synthetic, so recall cannot help and the answer is exactly checkable.', 'Large, so a reading is stable.'],
        cons: ['Templated language, so a model can learn the pattern and ace it without general reasoning.', 'Closed-world and open-world versions are easy to confuse, and scores are not comparable across them.', 'Saturated by large models, so it ranks mostly small ones.', 'Not run by us yet, and no published reading for the models we track.'],
      },
      {
        key: 'bbh', source: 'standard', board: 'none', noBoard: NO,
        name: 'BIG-Bench Hard', tag: 'industry standard · not yet read',
        about: 'Twenty-three of the hardest tasks in BIG-Bench, chosen because earlier models fell below the average human on them. The logic ones are logical deduction, boolean expressions, web of lies and tracking shuffled objects.',
        link: { href: 'https://arxiv.org/abs/2210.09261', label: 'BIG-Bench Hard (Suzgun et al., 2022)' },
        pros: ['The most widely reported general reasoning suite, so a number is understood everywhere.', 'Several tasks are exact algorithmic logic with a single right answer.', 'Small tasks, so a full run is cheap.'],
        cons: ['About 250 items a task, so a single task is noisy.', 'Twenty-three tasks mixed, and only a handful are logic: an overall score hides which.', 'Public since 2022 and near saturation for the frontier.', 'Not run by us yet, and no published reading for the models we track.'],
      },
      {
        key: 'zebralogic', source: 'standard', board: 'none', noBoard: NO,
        name: 'ZebraLogic', tag: 'industry standard · not yet read',
        about: 'Logic-grid puzzles (the "zebra" or Einstein puzzle): a grid of houses and attributes and a list of clues, solved by constraint satisfaction. The grid size is set by the author, so difficulty scales smoothly and a score is a curve against size.',
        link: { href: 'https://arxiv.org/abs/2502.01100', label: 'ZebraLogic (Lin et al., 2025)' },
        pros: ['Difficulty is tunable and a model\'s accuracy against puzzle size shows exactly where its reasoning gives out.', 'Exactly checkable, with no judge, and generated, so it is hard to have seen the puzzles.', 'A newer test used to compare reasoning models, so it is not yet saturated.'],
        cons: ['One narrow puzzle form, and models can be tuned for it.', 'Needs long reasoning, so a model that does not think in steps sits near the floor.', 'A small model will mostly show a zero, which separates nothing.', 'Not run by us yet, and no published reading for the models we track.'],
      },
      {
        key: 'musique', source: 'standard', board: 'none', noBoard: NO,
        name: 'MuSiQue', tag: 'industry standard · not yet read',
        about: 'Multi-hop questions of two to four hops, built by composing single-hop questions so that each hop needs the one before. It was made to close the shortcuts in earlier multi-hop sets, where a model could answer from a single paragraph.',
        link: { href: 'https://arxiv.org/abs/2108.00573', label: 'MuSiQue (Trivedi et al., 2022)' },
        pros: ['Built so that every hop is needed: harder to shortcut than HotpotQA, which a model can largely answer without the chain.', 'Two to four hops, so a score by hop count is a score for chaining.', 'Standard for multi-hop question answering, so there is a literature.'],
        cons: ['Without retrieved passages a small model\'s score mostly measures what it knows, not how it chains.', 'Scored by answer-string match (F1 and exact match), which is strict about wording.', 'Questions about real facts, so contamination is possible.', 'Not run by us yet, and no published reading for the models we track.'],
      },
      {
        key: 'babi', source: 'standard', board: 'none', noBoard: NO,
        name: 'bAbI', tag: 'industry standard · not yet read',
        about: 'Twenty synthetic question-answering tasks from Facebook AI Research, among them the original "two supporting facts" and "three supporting facts" tasks: a short story, and a question whose answer needs two or three of its sentences combined. The first chaining test.',
        link: { href: 'https://arxiv.org/abs/1502.05698', label: 'bAbI (Weston et al., 2015)' },
        pros: ['The oldest and cleanest chaining test: two or three supporting facts, exactly our question.', 'Synthetic and exact, with a controlled difficulty and no outside knowledge needed.', 'Tiny and instant to run.'],
        cons: ['Solved since about 2016, so a good score shows little: it is a floor, not a contest.', 'Templated stories from a small vocabulary, so a model can learn the templates.', 'Not run by us yet, and no published reading for the models we track.'],
      },
    ],
  },
  {
    key: 'knowledge',
    about: 'what a model holds: grade-school science read by loss, and two published factual-recall tests',
    tests: [
      {
        key: 'arc', source: 'ours', board: 'arc', art: '/art/test-arc.png',
        name: 'AI2 ARC', tag: 'Easy 2,376 · Challenge 1,172',
        about: 'Grade-school science, four answers a question. Read zero-shot with the option\'s own text as the continuation, the lowest mean loss the bet: no letters, no examples, no generation.',
        link: { href: 'https://allenai.org/data/arc', label: 'AI2 Reasoning Challenge (Clark et al., 2018)' },
        pros: ['Peer-recognised, and large enough (2,376 and 1,172) to read small differences.', 'Has a gradient under 1B, where most tests are flat: Easy ranks a class that nothing else can.', 'Zero-shot and loss-scored, so our ships and outside models are read identically.'],
        cons: ['Grade-school questions a pretraining corpus may well hold: contamination is not ruled out.', 'Challenge sits at or under chance for every model trained before 2025, so it ranks nothing at small sizes.', 'Not comparable with published ARC numbers, which are 25-shot and scored on the letter.', 'Saturates for large models, so it says little above the small class.'],
      },
      { key: 'omniscience-accuracy', source: 'published', board: 'published',
        pros: ['Reads broad factual recall on one scale, independently of the labs.', 'Separates models that guess from models that know, together with its non-hallucination half.'],
        cons: ['Published readings only, so we cannot rerun it or vouch for the method.', 'It rewards memorisation: for config work the facts are in the prompt, so a low score is not fatal.', 'Covers only the medium-class models we track here.'] },
      { key: 'omniscience-honesty', source: 'published', board: 'published',
        pros: ['Measures declining to answer instead of inventing one, the rate that matters when an invented key is worse than "I don\'t know".', 'Pairs with accuracy, so a model cannot look good by never answering.'],
        cons: ['Published only, and a refusal rate depends on how the model was prompted to abstain.', 'A model that refuses a lot scores well here and is less useful: read it beside accuracy.', 'Only the medium-class models we track have a reading.'] },
    ],
  },
  {
    key: 'reasoning',
    about: 'fluid reasoning and hard problems: ARC-AGI-2 is our reading (a pilot), and four published tests sit beside it',
    tests: [
      {
        key: 'arcagi2', source: 'ours', board: 'arcagi2', art: '/art/test-arcagi2.png',
        name: 'ARC-AGI-2', tag: 'pass@2 · 120 tasks',
        about: 'The canonical intelligence ranking: pass@2 on the 120-task evaluation set, grid puzzles with no language or domain knowledge to memorise. Published scores are the public leaderboard\'s; our reading is the Kipling ARC arm\'s, and it is a pilot.',
        link: { href: 'https://arcprize.org/arc-agi', label: 'ARC Prize: ARC-AGI-2' },
        pros: ['Built to resist memorisation: each task is new, with no language or domain knowledge to lean on.', 'The best-known measure of fluid reasoning, so a number means something outside this project.', 'A fixed 120-task set and pass@2, so scores are comparable between readings.'],
        cons: ['Scores are near zero for any small model prompted cold, so it does not separate models under about 4B.', 'Our readings are pilots on fewer tasks, and a pilot is never compared with a published score.', 'Two different contests under one name: prompted cold, or trained on the ARC tasks first.', 'Grids written as text are a hard format for a small model before reasoning even starts.'],
      },
      { key: 'gpqa-diamond', source: 'published', board: 'published',
        pros: ['Graduate-level science questions written to resist search, so a score is not just retrieval.', 'A broad reasoning floor that is widely reported.'],
        cons: ['About two hundred questions, so a few points are noise.', 'Multiple choice, so chance is not zero and prompting matters.', 'Near saturation for the frontier and possibly contaminated for newer models.', 'Published only, and it is not a coding or config test.'] },
      { key: 'hle', source: 'published', board: 'published',
        pros: ['The hardest closed-book questions in the field, so it does not saturate.', 'Wide subject coverage written by experts.'],
        cons: ['Every model we track is near the floor, so it separates nothing at these sizes.', 'Some questions have been disputed, so the ceiling is not a clean 100.', 'Published only, no tools, and no use for deciding what to build on.'] },
      { key: 'hmmt-feb-26', source: 'published', board: 'published',
        pros: ['Fresh competition mathematics, likelier to postdate a model\'s training than older sets.', 'A long chain of exact steps: the discipline a schema migration also needs.'],
        cons: ['A small problem set (a competition has few problems), so scores are coarse.', 'Maths only, and it rewards long reasoning budgets more than quick answers.', 'Published only, from one source, for the medium class.'] },
      { key: 'imo-answerbench', source: 'published', board: 'published',
        pros: ['Olympiad problems answered rather than proved: a short exact final answer that can be checked automatically.', 'The same shape as a config diff: one exact output.'],
        cons: ['Grades the answer, not the argument, so a lucky guess counts.', 'Hard enough that small models sit near the floor.', 'Published only, and we have not read its construction closely enough to vouch for it.'] },
    ],
  },
  {
    key: 'instruction',
    about: 'whether a model does what it is told: IFEval is ours, and three published tests push on constraints, turns and long prose',
    tests: [
      {
        key: 'ifeval', source: 'ours', board: 'ifeval', art: '/art/test-ifeval.png',
        name: 'IFEval', tag: '541 prompts',
        about: 'Five hundred and forty-one prompts, each with orders a program can check — no commas, three paragraphs, end with this phrase — read by the authors\' 25 verifiers. Prompt-level strict: every order in the prompt followed, or the prompt fails.',
        link: { href: 'https://arxiv.org/abs/2311.07911', label: 'Instruction-Following Evaluation (Zhou et al., 2023)' },
        pros: ['Programmatic checks and no judge: a score cannot be argued with.', 'Peer-recognised and cheap to run, so every checkpoint gets a reading.', 'Prompt-level strict is a hard bar: one missed order fails the prompt.'],
        cons: ['The constraints are easy and artificial, and the frontier is close to saturation.', 'Can be rigged: a model trained on the 541 prompts learns the checks, not instruction following (we mark those rows and never quote them bare).', 'Our reading is greedy with a 512-piece cap and a base model gets the prompt bare, so it is not comparable with published chat-template numbers.'],
      },
      { key: 'ifbench', source: 'published', board: 'published',
        pros: ['Hundreds of new, out-of-distribution constraints, so it is less likely to have been trained on than IFEval.', 'Verifiable by program rather than by a judge.'],
        cons: ['Published only, so we cannot rerun it.', 'The constraints are still artificial: following them exactly is not the same as following a house convention.', 'Only the medium class has a reading here.'] },
      { key: 'multi-if', source: 'published', board: 'published',
        pros: ['Instruction following across several turns and several languages: whether turn one\'s orders still hold at turn five.', 'Catches drift that a one-prompt test cannot.'],
        cons: ['Errors compound over turns, so a score mixes instruction following with memory.', 'The language mix means a low score may be a language gap, not an obedience gap.', 'Published only.'] },
      { key: 'life-bench', source: 'published', board: 'published',
        pros: ['Long-form writing under constraints on real tasks: closer to the page of prose we actually ask for.', 'Tests a page, not a one-line answer.'],
        cons: ['We cannot vouch for how it is graded: long-form scoring usually leans on a judge, which adds its own bias.', 'Less documented and less widely reported than IFEval.', 'Published only.'] },
    ],
  },
  {
    key: 'coding',
    about: 'writing code that runs: we measure no coding test yet, so both published tests stand alone',
    tests: [
      { key: 'artifactsbench', source: 'published', board: 'published',
        pros: ['The code is rendered and graded on what it looks and does: the closest published test to React and Astro component work.', 'Checks the result, not just that the code parses.'],
        cons: ['Grading a rendering usually needs a judge model, so it carries a judge\'s bias — we have not checked its method.', 'Published only, so we cannot rerun it.', 'Web artifacts only: it says little about backend or Python work.'] },
      { key: 'scicode', source: 'published', board: 'published',
        pros: ['Scientific computing written as code and run against its own tests: no judge, a program decides.', 'The harder end of "basic Python", where arithmetic and units have to be right.'],
        cons: ['Hard enough that small models sit near zero, so it ranks only the medium class and up.', 'Python and scientific domains only.', 'Published only, and not a test of editing an existing file.'] },
    ],
  },
  {
    key: 'agent',
    about: 'acting through tools until the errand is done: our drone tasks run browser, email and phone work but are not scored yet, and four published tests stand beside them',
    tests: [
      {
        key: 'drones', source: 'ours', board: 'none', noBoard: 'Not a benchmark yet: no task set is fixed and nothing scores a run, so there is no board. A fixed set of tasks with a pass or fail grade would make one.',
        name: 'Our drone tasks', tag: 'browser · email · phone, unscored',
        about: 'Our own drones run browser, email and phone tasks for real. They are not yet a scored benchmark: nothing grades a run pass or fail, so there is no board to show.',
        link: { href: '/orbitals/demiton', label: 'Demiton' },
        pros: ['The closest thing to the work we actually want an agent to do: real browsers, real mail, a real phone.', 'Ours, so we can make the tasks as hard and as particular as the work is.'],
        cons: ['Not a benchmark yet: no task set is fixed and nothing scores a run.', 'No outside model has been run on them, so there is nothing to compare.', 'Real services change under us, so a task may not repeat.'],
      },
      { key: 'bfcl-v4', source: 'published', board: 'published',
        pros: ['The standard function-calling board: picking the right tool, filling its arguments and declining when none fits.', 'Checked by program, with no judge.'],
        cons: ['Mostly single-turn calls, which are easier than a long errand.', 'Sensitive to how the tool schema is written, so scores move with the harness.', 'Published only.'] },
      { key: 'tau3-banking', source: 'published', board: 'published',
        pros: ['Multi-step tasks with tools and a policy: whether the agent finishes the errand, not whether it answers one turn.', 'The policy makes it a test of following rules while acting.'],
        cons: ['A simulated user makes runs vary, so scores carry run-to-run noise.', 'One narrow domain (banking), so it may not carry over.', 'Costly to run, and we have not run it.'] },
      { key: 'gdpval-v2', source: 'published', board: 'published',
        pros: ['Real professional work tasks judged against a human baseline: a broad general-agent measure.', 'Reads the quality of the finished answer, not a yes or no.'],
        cons: ['Scored Elo-style from judged comparisons, so it is relative and not a percentage.', 'Depends on a judge, with the bias that brings.', 'Published only.'] },
      { key: 'terminal-bench-2-1', source: 'published', board: 'published',
        pros: ['A shell, a task and no hints: the agent runs commands until the task passes, checked by program.', 'The nearest published test to editing files on a real machine.'],
        cons: ['A heavy harness, and scores depend on the scaffold around the model.', 'Small models sit near zero.', 'Published only, and it grades the agent as a whole, not the model.'] },
    ],
  },
  {
    key: 'long-context',
    about: 'finding and combining facts across a long context: we measure none yet, so the one published test stands alone',
    tests: [
      { key: 'aa-lcr', source: 'published', board: 'published',
        pros: ['Reasoning over long documents: finding and combining facts across far more than a config file holds.', 'Reads the headroom a schema dump would use.'],
        cons: ['Bounded by each model\'s context window, so a short-context model cannot be read at all.', 'Heavy to run, and we have not run it.', 'Published only, from one source.'] },
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
