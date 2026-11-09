// The shapes the JSON API returns, shared by the typed view modules. Extracted from the view monolith;
// each type names the fields server.py sends, with `[key: string]: unknown` left open so a reader can
// pick off the extra fields a specific panel adds without a cast.

/** One run (a voyage): the ledger's runs row, plus the fields server.py derives from its spec. */
export interface Run {
  run_id: string;
  name: string;
  ship?: string;
  status: string;
  started?: string;
  finished?: string;
  tokens_seen?: number;
  wall_minutes?: number;
  commit?: string;
  hardware?: string;
  preset?: string;
  seed?: number;
  [key: string]: unknown;
}

/** A metric series is [steps, values], as /api/metrics returns it. */
export type Series = number[][];

export type Metrics = Record<string, Series>;
