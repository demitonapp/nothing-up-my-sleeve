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
    key: 'logic', note: 'the logic and cause decks and chaining, beside LogiQA, ReClor, FOLIO and ProofWriter', label: 'Logic',
    ours: 'the logic deck (40 items, five relations: order, cause, membership, proportion, counterfactual), the cause deck (96 cause items), chaining two facts (the four tests: Nature’s breeder, mill, between, pigeonhole)',
    published: 'the industry standards, none read on a model we track yet: LogiQA 2.0, ReClor, FOLIO, ProofWriter, BIG-Bench Hard, ZebraLogic, MuSiQue, bAbI', publishedKeys: [],
  },
  {
    key: 'knowledge', note: 'AI2 ARC, beside AA-Omniscience', label: 'Knowledge',
    ours: 'AI2 ARC (Easy 2,376 / Challenge 1,172)',
    published: 'AA-Omniscience accuracy and non-hallucination', publishedKeys: ['omniscience-accuracy', 'omniscience-honesty'],
  },
  {
    key: 'reasoning', note: 'ARC-AGI-2, beside GPQA, HLE, HMMT and IMO', label: 'Reasoning',
    ours: 'ARC-AGI-2 (pass@2, 120 tasks)',
    published: 'GPQA Diamond, HLE, HMMT Feb 2026, IMO-AnswerBench', publishedKeys: ['gpqa-diamond', 'hle', 'hmmt-feb-26', 'imo-answerbench'],
  },
  {
    key: 'instruction', note: 'IFEval, beside IFBench, Multi-IF and LIFE-Bench', label: 'Instruction following',
    ours: 'IFEval (541 prompts)',
    published: 'IFBench, Multi-IF, LIFE-Bench', publishedKeys: ['ifbench', 'multi-if', 'life-bench'],
  },
  {
    key: 'coding', note: 'published only: ArtifactsBench, SciCode', label: 'Coding',
    ours: '—',
    published: 'ArtifactsBench, SciCode', publishedKeys: ['artifactsbench', 'scicode'],
  },
  {
    key: 'agent', note: 'our drone tasks, beside BFCL, TAU3, GDPval and Terminal-Bench', label: 'Agent',
    ours: 'our browser/email/phone drone tasks (not yet a scored benchmark)',
    published: 'BFCL v4, TAU3-Banking, GDPval v2, Terminal-Bench 2.1', publishedKeys: ['bfcl-v4', 'tau3-banking', 'gdpval-v2', 'terminal-bench-2-1'],
  },
  {
    key: 'long-context', note: 'published only: AA-LCR', label: 'Long context',
    ours: '—',
    published: 'AA-LCR', publishedKeys: ['aa-lcr'],
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
  knowledge: { art: '/art/test-arc.png', tag: 'AI2 ARC', about: 'What a model holds: grade-school science read by loss, beside two published tests of factual recall.', link: { href: 'https://allenai.org/data/arc', label: 'AI2 Reasoning Challenge (Clark et al., 2018)' } },
  reasoning: { art: '/art/test-arcagi2.png', tag: 'ARC-AGI-2', about: 'Fluid reasoning and hard problems: ARC-AGI-2, our pilot reading, beside four published tests.', link: { href: 'https://arcprize.org/arc-agi', label: 'ARC Prize: ARC-AGI-2' } },
  instruction: { art: '/art/test-ifeval.png', tag: 'IFEval', about: 'Whether a model does what it is told: IFEval, beside three published tests of constraints, turns and long prose.', link: { href: 'https://arxiv.org/abs/2311.07911', label: 'Instruction-Following Evaluation (Zhou et al., 2023)' } },
  coding: { tag: 'published only', about: 'Writing code that runs. We read no coding test ourselves yet.', link: { href: 'https://scicode-bench.github.io/', label: 'SciCode (Tian et al., 2024)' } },
  agent: { tag: 'drone tasks, unscored', about: 'Acting through tools until the errand is done. Our drones run browser, email and phone tasks, but nothing scores them yet.', link: { href: 'https://gorilla.cs.berkeley.edu/leaderboard.html', label: 'Berkeley Function Calling Leaderboard' } },
  'long-context': { tag: 'published only', about: 'Finding and combining facts across a context far longer than a page. We read no long-context test ourselves yet.', link: { href: 'https://artificialanalysis.ai/', label: 'Artificial Analysis, AA-LCR' } },
  abilities: { art: '/art/test-faces.png', tag: 'the four Faces', about: 'The four Faces: abilities a ship earns when its own measure passes a mark, beside Qwen 3 4B, the reference chainer.', link: { href: '/orbitals/demiton/discoveries/stars', label: 'Discoveries, Stars: the four Faces' } },
};

/** Old ?test= addresses that still land on a card: chaining is now the Logic card's. */
export const TEST_ALIASES: Record<string, string> = { chaining: 'logic' };
