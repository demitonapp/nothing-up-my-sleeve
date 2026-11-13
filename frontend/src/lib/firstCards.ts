// The two cards a new visitor meets (13 November, Justin: "two cards for new users to the site, Nothing up my
// sleeve latest epub which the user can download, email to their kindle or read, or another card which is kinda
// like a join a faction card whereby people can help with Nothing up my sleeve's mission"), and the four sides a
// visitor can join (his answer the same day: "4 cards which is how they can help. Investor, Researcher, GPU
// provider, Corpus provider"), with two ways to start that need nobody's leave (running a model on your own
// machine, building with us).
//
// This file is the words and the addresses; the islands draw them. Nothing here is fetched: the public site has
// no API, so joining is a note on the project's public repository and what a browser remembers stays in it.

import book from '@/data/book.json';

export const BOOK = book;

/** The project's public repository, where a visitor raises a hand and where the code is. */
export const REPO = 'https://github.com/demitonapp/nothing-up-my-sleeve';

/** Amazon's own page for sending a file to a Kindle without email. */
export const SEND_TO_KINDLE = 'https://www.amazon.com/sendtokindle';

export const MISSION = 'Language models for everybody: a small kernel, built in the open, that anyone can read, run and check, starting with the smallest kernel of English.';

export type FactionKey = 'investor' | 'researcher' | 'gpu' | 'corpus';

export interface Faction {
  key: FactionKey;
  name: string;
  /** With its article, for "Join as …". */
  as: string;
  brings: string;
  about: string;
}

export const FACTIONS: readonly Faction[] = [
  {
    key: 'investor',
    name: 'Investor',
    as: 'an Investor',
    brings: 'Money for the voyages.',
    about: 'Training runs are paid for by the hour, and the people who plan and read them have to eat. The kernel is open and non-commercial, so start by asking what that means for you.',
  },
  {
    key: 'researcher',
    name: 'Researcher',
    as: 'a Researcher',
    brings: 'A question, a test or a method.',
    about: 'Every ship is read on a public leaderboard, and the texts and runs behind it are listed, so a result here can be checked by anyone. Bring a test the fleet should sit, or a way of reading what a small model has learned.',
  },
  {
    key: 'gpu',
    name: 'GPU provider',
    as: 'a GPU provider',
    brings: 'Hours on a card.',
    about: 'The first fifty-million-parameter ship took 140 minutes on one hired RTX 4090. Tell us what you have and when it is idle, and we will work out how a voyage reaches it.',
  },
  {
    key: 'corpus',
    name: 'Corpus provider',
    as: 'a Corpus provider',
    brings: 'Texts, with their papers.',
    about: 'Every text a ship reads is a row in a published list with its source. Bring writing you hold the rights to, or know to be free, and say where it came from, and it can become rows.',
  },
];

/** The note a visitor opens to join a side: a new issue on the public repository, its title filled in. Nothing
 *  about the visitor is in the address; they write the note themselves. */
export const joinHref = (f: Faction): string =>
  `${REPO}/issues/new?title=${encodeURIComponent(`Joining as ${f.as}`)}&body=${encodeURIComponent('What I can bring:\n\nWhat I would like to know first:\n')}`;

// What this browser remembers. Every read and write is guarded: a private window has no storage, and the pages
// must draw the same without it.
const WELCOME_KEY = 'thorp.welcome.hidden';
const SIDE_KEY = 'thorp.side';
const KINDLE_KEY = 'thorp.kindle.address';
const PLACE_KEY = 'thorp.book.place';

const read = (k: string): string | null => { try { return localStorage.getItem(k); } catch { return null; } };
const write = (k: string, v: string | null): void => {
  try { if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch { /* no storage here */ }
};

export const welcomeHidden = (): boolean => read(WELCOME_KEY) === '1';
export const hideWelcome = (hidden: boolean): void => write(WELCOME_KEY, hidden ? '1' : null);
export const side = (): FactionKey | null => { const s = read(SIDE_KEY); return FACTIONS.some((f) => f.key === s) ? (s as FactionKey) : null; };
export const setSide = (k: FactionKey | null): void => write(SIDE_KEY, k);
export const kindleAddress = (): string => read(KINDLE_KEY) || '';
export const rememberKindle = (address: string | null): void => write(KINDLE_KEY, address);
export const bookPlace = (): string | null => read(PLACE_KEY);
export const setBookPlace = (href: string): void => write(PLACE_KEY, href);

/** 4469769 → "4.5 MB". */
export const megabytes = (bytes: number): string => `${(bytes / 1e6).toFixed(1)} MB`;

/** "2026-11-13" → "13 November 2026". */
export const longDate = (iso: string): string => {
  const [y, m, d] = iso.split('-').map(Number);
  const months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  return y && m && d ? `${d} ${months[m - 1]} ${y}` : iso;
};
