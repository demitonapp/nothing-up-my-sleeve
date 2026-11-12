// The tricks of the trade on the two axes (13 November, Justin: "merge the tricks into discoveries", choosing "tricks
// join the map"). Every trick is a behaviour: what a model can do, judged from outside by its bets. Its object of study
// follows its waypoint: Reading (the form of the language, copying what came before, keeping a tone) is done at the
// moment of use, so inference and prompting; the other six (knowing, counting, reasoning, mathematics, physics,
// discovery) are what a model knows and whether it can put it together, so knowledge and memory.
//
// The tricks come from data/tricks.json, written from thorp/dash/tricks.py's KNOWN_TRICKS by `python -m
// thorp.dash.trick_keys`, so the map needs no live payload and a new trick joins it when the file is rewritten. Each
// links to its own page under Demiton's discoveries.

import tricks from '../data/tricks.json';
import { DEMITON_DISCOVERIES as DB } from './discoveryPaths';

export interface MapTrick { key: string; name: string; does: string; waypoint: string; source: string | null; href: string }

/** The waypoint a trick sits on decides its object of study. */
const OBJECT_OF_WAYPOINT: Record<string, string> = {
  reading: 'inference',
  knowing: 'knowledge', counting: 'knowledge', reasoning: 'knowledge',
  mathematics: 'knowledge', physics: 'knowledge', discovery: 'knowledge',
};

export const WAYPOINTS: { key: string; name: string }[] = tricks.waypoints;

export const TRICKS: (MapTrick & { kind: string; object: string })[] = tricks.detail.map((t) => ({
  ...t,
  href: `${DB}/${t.key}`,
  kind: 'behaviour',
  object: OBJECT_OF_WAYPOINT[t.waypoint] || 'knowledge',
}));

/** The tricks in one category of an axis ('kind' or 'object'), in the ladder's order. */
export const tricksIn = (axisKey: string, cat: string): MapTrick[] =>
  TRICKS.filter((t) => (axisKey === 'kind' ? t.kind : t.object) === cat);

/** The same tricks grouped by waypoint, in the ladder's order, leaving out empty waypoints. */
export const byWaypoint = (list: MapTrick[]): { key: string; name: string; tricks: MapTrick[] }[] =>
  WAYPOINTS.map((w) => ({ ...w, tricks: list.filter((t) => t.waypoint === w.key) })).filter((g) => g.tricks.length);
