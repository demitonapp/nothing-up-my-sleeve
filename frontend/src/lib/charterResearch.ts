// The field's discoveries tied to the master charter's rows (12 November, Justin: "what needs to happen for us to
// fold all the research against each category into our fleet so that we can make decisions for the full charter,
// sign it off and then launch the full fleet", then "Yes, build the map").
//
// One list of bearings: a discovery of lib/fieldMap.ts, the charter rows it bears on (the keys of thorp/launch.py's
// PARAMS, `ship.layers` …) and what it means at the fleet's sizes. The charter page reads the list by row ("the field
// says", beside the goals that decide the row) and a discovery's card reads it by discovery ("bears on the charter"),
// so the two cannot disagree. backend/tests/test_charter_research.py fails when a key here names no row or no
// discovery.
//
// `says` is the reading for THIS fleet, written 12 November 2026: the finding is the discovery's own text, and what
// follows from it at 0.3M to 40M parameters is ours. Where it leans on a reading of ours it says which.
//
// The bar the charter is read against is Justin's of the same evening: "I want the first Nothin up my sleeve to have
// a reasoining variant, tool calling, decent context window and be as good as possible on all our tests on the
// leaderboard". GAPS are the questions a waiting row asks that no discovery on the map answers; MISSING_ROWS are the
// rows that bar needs and the charter does not have.

import { DISCOVERIES, OBJECTS, slugOf, type FieldDiscovery } from './fieldMap';
import { DEMITON_DISCOVERIES as DB } from './discoveryPaths';

/** The master charter's rows as the page names them (group: row). Kept beside thorp/launch.py's GROUPS by the test. */
export const CHARTER_ROWS: Record<string, string> = {
  'ship.layers': 'the ship: layers',
  'ship.heads': 'the ship: query heads',
  'ship.kv_heads': 'the ship: KV heads',
  'ship.width': 'the ship: width',
  'ship.context': 'the ship: context',
  'ship.positions': 'the ship: positions',
  'ship.built': 'the ship: built',
  'tokeniser.pieces': 'the tokeniser: pieces',
  'tokeniser.byte_fallback': 'the tokeniser: byte fallback',
  'tokeniser.train_on': 'the tokeniser: trained on',
  'tokeniser.symbols': 'the tokeniser: control symbols',
  'reads.recipe': 'what it reads: recipe',
  'reads.passes': 'what it reads: passes',
  'reads.clean': 'what it reads: clean',
  'reads.order': 'what it reads: order',
  'reads.refuse': 'what it reads: refuses',
  'scaffold.pins': 'the scaffold: pins',
  'scaffold.riddles': 'the scaffold: riddles',
  'scaffold.weight': 'the scaffold: weight',
  'scaffold.hold': 'the scaffold: hold',
  'scaffold.fade': 'the scaffold: fade',
  'scaffold.release': 'the scaffold: release',
  'training.optimiser': 'the training: optimiser',
  'training.lr': 'the training: learning rate',
  'training.warmup': 'the training: warm-up',
  'training.batch': 'the training: batch',
  'training.schedule': 'the training: schedule',
  'training.grad_clip': 'the training: grad clip',
  'training.precision': 'the training: precision',
  'leg.inherits': 'the return leg: inherits',
  'leg.turns': 'the return leg: turns',
  'leg.stages': 'the return leg: stages',
  'leg.lr': 'the return leg: learning rate',
  'leg.pull': 'the return leg: the pull',
};

export interface Bearing { discovery: string; rows: string[]; says: string }

export const BEARINGS: Bearing[] = [
  // training and scale
  { discovery: 'power-law-scaling', rows: ['ship.layers', 'ship.width'], says: 'Each class up should read the unseen books better by a steady step. A class that does not has a fault to find before its hull is signed: the draft’s 9m read 1.937 bits a byte on 12 November where the 9m before it read 1.579.' },
  { discovery: 'compute-optimal', rows: ['reads.passes', 'reads.recipe'], says: 'About twenty tokens a parameter. Ogden v0.1 is about 67M tokens a pass, 269M over four: enough for the 21m (about 224M wanted) and a third of what the 50m wants (about 800M). The 50m needs more text, not more passes.' },
  { discovery: 'data-constrained', rows: ['reads.passes'], says: 'Four passes is as far as the field supports reading the same text again; a fifth is worth less than new books.' },
  { discovery: 'mup', rows: ['training.lr', 'training.warmup'], says: 'The draft sets a rate for each class by hand. Under this parametrisation a rate tuned at the 300k would carry up the ladder. It is not in the draft, so each class’s rate rests on that class’s own rehearsals.' },
  { discovery: 'distillation', rows: ['leg.stages', 'reads.recipe'], says: 'A teacher’s answers, with its reasoning written out and its tool calls, are the practical source for a reasoning leg’s and a tool leg’s corpus. The draft’s leg reads a dialogue shelf and a conversation list and nothing distilled.' },
  { discovery: 'implicit-reasoners', rows: ['reads.recipe', 'scaffold.riddles'], says: 'Chaining two facts without writing the step is learned from the share of inferred facts in the text, over long training, not from a pull on a head. It argues for chained items in the corpus rather than a bridge riddle.' },
  // architecture
  { discovery: 'rope', rows: ['ship.positions', 'ship.context'], says: 'Signed. Rotary positions need no table, so the window can be lengthened without another parameter. Whether a leg can read through a longer window than its base was trained on has not been tried here.' },
  { discovery: 'gqa', rows: ['ship.kv_heads'], says: 'The field’s saving is a large model’s key-value cache at inference. At these sizes there is nothing to save: read at 300k (two seeds) and 9m (kipling:6), the language unchanged, half a gigabyte of 13.5 saved, the comparator lower. One KV head per query head.' },
  { discovery: 'flash-attention', rows: ['ship.context'], says: 'A window’s cost is in holding the attention map. This Mac’s kernel holds every head’s whole map for the backward pass, so memory grows with the square of the window (the 21m: 1.2 GB a window at 1,024 pieces, 9.2 at 4,096); a hired GPU’s kernel need not. Above 1,024 the 21m and the 50m sail abroad.' },
  // data
  { discovery: 'textbook-quality', rows: ['reads.recipe'], says: 'Teaching-grade text lets a small model match a much larger one on reasoning. Every class, 300k to 50m, read AI2 ARC at chance on Ogden’s books (12 November): the lever for that test is what the fleet reads, not its hull.' },
  { discovery: 'tinystories', rows: ['reads.recipe'], says: 'The case for Ogden’s Basic English at the 9m and below, and for teaching conversation, reasoning and tool calls in the same small vocabulary rather than in the wide English of a teacher’s output.' },
  { discovery: 'dedup', rows: ['reads.clean'], says: 'The row names how a book is cleaned (unwrapped, or raw) and says nothing of near-duplicates: two editions of one book in the list would be read eight times in four passes.' },
  { discovery: 'glitch-tokens', rows: ['tokeniser.symbols', 'tokeniser.train_on'], says: 'Every control symbol the fleet declares, the thinking and tool marks included, has to be read many times in pretraining or in the leg, or be left out. A mark kept in reserve is a glitch token.' },
  { discovery: 'model-collapse', rows: ['reads.recipe', 'leg.stages'], says: 'A distilled reasoning or tool corpus is a seasoning on real books, made once from a teacher and never from our own ships’ writing.' },
  // post-training
  { discovery: 'superficial-alignment', rows: ['leg.stages', 'leg.lr', 'leg.inherits'], says: 'A leg should be short and gentle, and cannot give what pretraining did not. The draft’s talk leg agrees on the first (the lower rate kept the language) and shows the second (the reply barely reads its question: 0.037 bits a byte).' },
  // inference and prompting
  { discovery: 'chain-of-thought', rows: ['leg.stages'], says: 'The field’s gains are in models far larger than the fleet’s. At 3M to 40M parameters the reasoning variant is a bet, to be rehearsed at the 9m before the 21m and the 50m are laid.' },
  { discovery: 'test-time-compute', rows: ['leg.stages', 'tokeniser.symbols'], says: 'A reasoning leg needs marks to open and close the thinking and a budget for it. The draft has neither: the symbols locked on 12 November leave thinking marks out.' },
  { discovery: 'lost-in-the-middle', rows: ['ship.context'], says: 'A longer window is read worst in its middle. A tool’s definition and the question belong at the start and the end of the prompt; a long window is room, not a store.' },
  // internals
  { discovery: 'induction-heads', rows: ['scaffold.pins', 'scaffold.release'], says: 'The pair forms unaided in models trained without help. The fleet’s probe at 300k agrees on the first card (previous-word is held by heart) and not on the second (induction still leans on the pull at 80% of the voyage), which is the case for no release.' },
  { discovery: 'attention-sinks', rows: ['tokeniser.symbols'], says: 'The reason every window opens with <bos>: it is where spare attention rests, and keeping it lets a ship run on past the length it trained at.' },
  // knowledge and memory
  { discovery: 'knowledge-capacity', rows: ['reads.recipe', 'ship.width'], says: 'What a class can know is set by its size: under a megabit at the 300k, about ten megabytes at the 50m. And a fact stated once, one way, is not stored so that it can be got out again: the corpus has to say what matters in several phrasings.' },
  { discovery: 'reversal-curse', rows: ['reads.recipe'], says: 'Text written to teach (catechisms, question and answer) has to state its facts both ways round.' },
  { discovery: 'compositionality-gap', rows: ['scaffold.riddles'], says: 'A larger class will not chain two facts by being larger.' },
  { discovery: 'two-hop-curse', rows: ['scaffold.riddles', 'leg.stages'], says: 'The field’s reason the bridge riddle did not light at the 9m (card_census:2), and the case for a reasoning leg: facts learned apart are chained when the middle step is written out.' },
  { discovery: 'latent-multi-hop', rows: ['scaffold.riddles'], says: 'Where silent chaining works at all it is in a large model’s middle layers. The bridge riddle pulled at two-thirds depth in a 9m and nothing lit.' },
  // evaluation
  { discovery: 'contamination', rows: ['leg.stages'], says: 'The 0.906 a 9m reads on IFEval is from a leg taught on the test’s own prompts. A leg judged on a test leaves its scored prompts out of its stages: the held-out split (360 taught, 139 kept back) is written and has not been sailed at the 9m.' },
];

export interface ResearchGap { key: string; rows: string[]; question: string; why: string }

/** What a waiting row asks that no discovery on the map answers: a reading pass, before a voyage is spent on it. */
export const GAPS: ResearchGap[] = [
  { key: 'hull', rows: ['ship.layers', 'ship.width', 'ship.heads'], question: 'Deep against wide at one to forty million parameters: what does depth buy at a fixed count, and what does it cost in speed?', why: 'The hull pair (kipling:8) reads it at the 1m alone; the 9m, 21m and 50m have no pair.' },
  { key: 'pieces', rows: ['tokeniser.pieces'], question: 'How many pieces suit a model this small, and should the count grow with the class?', why: 'One 9m reading at 4,096 pieces (kipling:10), inside the spread two like voyages show.' },
  { key: 'window', rows: ['ship.context'], question: 'What does a tool call with its reasoning need in pieces, and can a ship be pretrained at one window and taught its leg at a longer one?', why: 'The 9m at 2,048 (kipling:9) read only whether the books read better. They did not.' },
  { key: 'tools', rows: ['tokeniser.symbols', 'leg.turns'], question: 'How is tool calling taught to a small model: the marks, the form of a call and its result, and how many examples?', why: 'Nothing on the map is about tool calling, and no ship of ours has been taught it.' },
  { key: 'reasoning', rows: ['leg.stages'], question: 'How is written-out reasoning taught to a model of a few million parameters, and from what size does it help?', why: 'The map’s chain-of-thought discoveries are all from large models.' },
  { key: 'science', rows: ['reads.recipe'], question: 'What must a corpus hold, and how much of it, for a small model to answer grade-school science?', why: 'AI2 ARC at chance at every class; kipling:11’s arms read the language and the cards, not that test.' },
  { key: 'scaffold', rows: ['scaffold.weight', 'scaffold.hold', 'scaffold.fade', 'scaffold.release'], question: 'Has anyone pulled chosen heads toward a pattern during pretraining, and what did holding and letting go do?', why: 'These rows rest on the fleet’s own readings alone (the 300k probe, the release arms).' },
  { key: 'recipe', rows: ['training.optimiser', 'training.warmup', 'training.batch', 'training.schedule', 'training.grad_clip'], question: 'What do the published small-model recipes use for the optimiser, warm-up, batch, schedule and clip at this size?', why: 'Carried from the draft; rehearsed at 300k and 9m, never on v0.0.6 at the 21m or the 50m.' },
];

export interface MissingRow { key: string; group: string; name: string; why: string; discoveries: string[] }

/** Rows the bar of 12 November needs and the charter does not have. */
export const MISSING_ROWS: MissingRow[] = [
  { key: 'thinking-marks', group: 'the tokeniser', name: 'thinking and tool marks', why: 'The eight symbols locked on 12 November leave them out. They belong in the tokeniser before any base ship is laid, since every leg reads with its base’s pieces.', discoveries: ['glitch-tokens', 'test-time-compute'] },
  { key: 'reasoning-leg', group: 'the return leg', name: 'the reasoning leg', why: 'Its stages, its corpus and its thinking budget. No corpus, evaluator or voyage exists.', discoveries: ['chain-of-thought', 'two-hop-curse', 'distillation'] },
  { key: 'tool-leg', group: 'the return leg', name: 'the tool leg', why: 'The form of a call and its result, and the corpus that teaches it. No corpus, evaluator or voyage exists.', discoveries: ['distillation', 'superficial-alignment'] },
  { key: 'leg-window', group: 'the return leg', name: 'the leg’s window', why: 'A leg may need a longer window than the books do. Today the leg takes its base’s.', discoveries: ['rope', 'flash-attention', 'lost-in-the-middle'] },
  { key: 'feed-forward', group: 'the ship', name: 'feed-forward layer and normalisation', why: 'The charter has no row for either, so what the fleet is built with is not signed.', discoveries: ['glu'] },
  { key: 'bar', group: 'the bar', name: 'leaderboard targets, class by class', why: '"As good as possible on all our tests" has no number to be judged against, and the one high reading (IFEval) is on taught prompts.', discoveries: ['contamination', 'emergence-mirage'] },
];

const BY_KEY: Record<string, FieldDiscovery> = Object.fromEntries(DISCOVERIES.map((d) => [d.key, d]));

export const discoveryOf = (key: string): FieldDiscovery | null => BY_KEY[key] || null;

/** A discovery's card: its object-of-study page, at its own anchor. */
export const discoveryHref = (key: string): string => {
  const d = BY_KEY[key];
  const cat = d ? OBJECTS.find((c) => c.key === d.object) : null;
  return `${DB}/object-of-study/${cat ? slugOf(cat) : ''}#${key}`;
};

export interface RowBearing { discovery: FieldDiscovery; says: string }

/** What the field says on one charter row, in the map's order. */
export const bearingsOn = (row: string): RowBearing[] =>
  BEARINGS.filter((b) => b.rows.includes(row) && BY_KEY[b.discovery]).map((b) => ({ discovery: BY_KEY[b.discovery], says: b.says }));

/** The charter rows one discovery bears on, and what it means for the fleet. */
export const bearingOf = (discovery: string): Bearing | null => BEARINGS.find((b) => b.discovery === discovery) || null;

export const gapsOn = (row: string): ResearchGap[] => GAPS.filter((g) => g.rows.includes(row));

/** The tally the charter page opens on: how many discoveries bear on how many rows, and the rows the map is silent on. */
export const researchTally = (rows: string[]): { discoveries: number; covered: number; silent: string[] } => {
  const covered = rows.filter((r) => bearingsOn(r).length > 0);
  return { discoveries: BEARINGS.length, covered: covered.length, silent: rows.filter((r) => !covered.includes(r)) };
};
