// The leaderboard's categories of test (12 November, Justin's table): one card each on /leaderboard, and
// one entry each in the ⌘K palette. For every category, the tests we measure ourselves and the published
// tests beside them (their readings are data/benchmarks.json: Artificial Analysis's, not ours). Pure
// data, no DOM, so the landing and the palette cannot disagree about the list.

export interface TestCategory {
  /** The ?test= address of the card on /leaderboard. */
  key: string;
  label: string;
  /** One short line for the palette: what the card holds. */
  note: string;
  /** What we measure ourselves, in words; '—' where we measure nothing yet. */
  ours: string;
  /** The published tests, in words; '—' where none is tracked. */
  published: string;
  /** benchmarks.json test keys behind `published`, drawn on the back of the card. */
  publishedKeys: string[];
}

export const TEST_CATEGORIES: TestCategory[] = [
  {
    key: 'logic', note: 'the logic and cause decks and chaining, beside HotpotQA, BIG-Bench Hard, MuSiQue, bAbI and ProofWriter', label: 'Logic',
    ours: 'the logic deck (40 items, five relations: order, cause, membership, proportion, counterfactual), the cause deck (96 cause items), chaining two facts (the four tests: Nature’s breeder, mill, between, pigeonhole)',
    published: 'the five most-cited industry standards, none read on a model we track yet: HotpotQA, BIG-Bench Hard, MuSiQue, bAbI, ProofWriter', publishedKeys: [],
  },
  {
    key: 'knowledge', note: 'AI2 ARC, beside MMLU, TriviaQA, Natural Questions, MMLU-Pro and SimpleQA', label: 'Knowledge',
    ours: 'AI2 ARC (Easy 2,376 / Challenge 1,172)',
    published: 'MMLU, TriviaQA, Natural Questions, MMLU-Pro, SimpleQA (none read yet)', publishedKeys: [],
  },
  {
    key: 'reasoning', note: 'ARC-AGI-2, beside GSM8K, MATH, GPQA, ARC-AGI-1 and HLE', label: 'Reasoning',
    ours: 'ARC-AGI-2 (pass@2, 120 tasks)',
    published: 'GSM8K, MATH, GPQA Diamond, ARC-AGI-1, HLE (Artificial Analysis has readings for GPQA Diamond and HLE)', publishedKeys: ['gpqa-diamond', 'hle'],
  },
  {
    key: 'instruction', note: 'IFEval, beside MT-Bench, Arena-Hard, InFoBench, IFBench and Multi-IF', label: 'Instruction following',
    ours: 'IFEval (541 prompts)',
    published: 'MT-Bench, Arena-Hard, InFoBench, IFBench, Multi-IF (Artificial Analysis has readings for IFBench and Multi-IF)', publishedKeys: ['ifbench', 'multi-if'],
  },
  {
    key: 'coding', note: 'published only: HumanEval, MBPP, SWE-bench, LiveCodeBench, EvalPlus', label: 'Coding',
    ours: '—',
    published: 'HumanEval, MBPP, SWE-bench, LiveCodeBench, EvalPlus (none read yet)', publishedKeys: [],
  },
  {
    key: 'agent', note: 'our drone tasks, beside WebArena, AgentBench, τ-bench, BrowseComp and OSWorld', label: 'Agent',
    ours: 'our browser/email/phone drone tasks (not yet a scored benchmark)',
    published: 'WebArena, AgentBench, τ-bench, BrowseComp, OSWorld (none read yet)', publishedKeys: [],
  },
  {
    key: 'long-context', note: 'published only: LongBench, RULER, LongBench v2, InfiniteBench, L-Eval', label: 'Long context',
    ours: '—',
    published: 'LongBench, RULER, LongBench v2, InfiniteBench, L-Eval (none read yet)', publishedKeys: [],
  },
  {
    key: 'abilities', note: 'the four Faces', label: 'Abilities',
    ours: 'the four Faces: Nevermore, Counter, Scales, Mover',
    published: '—', publishedKeys: [],
  },
];

/** What a category's card says on the landing (and what opens its own page): its plate, the one line under it, and
 *  where its main test is published. The size pages' cards (CategoryCards.tsx) say their own, size-specific words. */
export const CATEGORY_FACE: Record<string, { art?: string; tag: string; about: string; link: { href: string; label: string } }> = {
  logic: { art: '/art/test-chaining.png', tag: 'the decks and the chaining tests', about: 'Can it reason from what it is given? The logic and cause decks are ours, and the four chaining tests ask two premises for one conclusion neither gives alone: the fix two bearings make on a chart.', link: { href: '/orbitals/demiton/discoveries/tests?test=chaining', label: 'Discoveries, Tests: chaining two facts' } },
  knowledge: { art: '/art/test-arc.png', tag: 'AI2 ARC', about: 'What a model holds: grade-school science read by loss, beside the five most-cited tests of knowledge.', link: { href: 'https://allenai.org/data/arc', label: 'AI2 Reasoning Challenge (Clark et al., 2018)' } },
  reasoning: { art: '/art/test-arcagi2.png', tag: 'ARC-AGI-2', about: 'Fluid reasoning and hard problems: ARC-AGI-2, our pilot reading, beside the five most-cited tests.', link: { href: 'https://arcprize.org/arc-agi', label: 'ARC Prize: ARC-AGI-2' } },
  instruction: { art: '/art/test-ifeval.png', tag: 'IFEval', about: 'Whether a model does what it is told: IFEval, beside the five most-cited tests, from graded constraints to judged conversations.', link: { href: 'https://arxiv.org/abs/2311.07911', label: 'Instruction-Following Evaluation (Zhou et al., 2023)' } },
  coding: { tag: 'published only', about: 'Writing code that runs. We read no coding test ourselves yet.', link: { href: 'https://arxiv.org/abs/2107.03374', label: 'HumanEval (Chen et al., 2021)' } },
  agent: { tag: 'drone tasks, unscored', about: 'Acting through tools until the errand is done. Our drones run browser, email and phone tasks, but nothing scores them yet.', link: { href: 'https://arxiv.org/abs/2307.13854', label: 'WebArena (Zhou et al., 2024)' } },
  'long-context': { tag: 'published only', about: 'Finding and combining facts across a context far longer than a page. We read no long-context test ourselves yet.', link: { href: 'https://arxiv.org/abs/2308.14508', label: 'LongBench (Bai et al., 2024)' } },
  abilities: { art: '/art/test-faces.png', tag: 'the four Faces', about: 'The four Faces: abilities a ship earns when its own measure passes a mark, beside Qwen 3 4B, the reference chainer.', link: { href: '/orbitals/demiton/discoveries/stars', label: 'Discoveries, Stars: the four Faces' } },
};

/** Old ?test= addresses that still land on a card: chaining is now the Logic card's. */
export const TEST_ALIASES: Record<string, string> = { chaining: 'logic' };
