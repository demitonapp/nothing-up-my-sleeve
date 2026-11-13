// The public edition's build step (13 November; the list of what it leaves out is src/lib/edition.ts).
//
// Astro builds every file under src/pages and has no switch to skip one, and a page cannot opt out of a
// static build (prerender = false needs a server adapter). So the public build renders the site, then this
// step removes, before the output is final:
//   1. every page whose address is private (Demiton and everything behind it, the settings),
//   2. every script or stylesheet no remaining page can reach, so the private islands' code does not ship,
// and it lists any link a remaining page still renders into a private address. In dev
// (PUBLIC_EDITION=1 pnpm dev) the same addresses answer 404, so the public site can be walked before a build.
// It does nothing at all in the private build.
import { readdirSync, readFileSync, rmSync, rmdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { isPrivatePath } from '../src/lib/edition.ts';

const walk = (dir) => readdirSync(dir).flatMap((name) => {
  const p = join(dir, name);
  return statSync(p).isDirectory() ? walk(p) : [p];
});

/** The address a built page answers: `ships/300k/index.html` is /ships/300k, `404.html` is /404. */
const routeOf = (root, file) => {
  const rel = relative(root, file).split(sep).join('/');
  if (rel === 'index.html') return '/';
  return '/' + rel.replace(/\/index\.html$/, '').replace(/\.html$/, '');
};

const removeEmptyDirs = (dir) => {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) removeEmptyDirs(p);
  }
  if (!readdirSync(dir).length) rmdirSync(dir);
};

/** Remove the scripts and stylesheets no remaining page reaches: from each page, follow every file name its HTML
 *  names, then every file name those scripts name (static imports, dynamic imports and Vite's preload lists all
 *  spell the file name out), and drop the rest. A name is only ever over-matched, never missed, so a file a
 *  page needs is never removed. */
function pruneUnreachable(root, pages) {
  const code = walk(root).filter((f) => /\.(m?js|css)$/.test(f));
  const byName = new Map(code.map((f) => [f.slice(f.lastIndexOf(sep) + 1), f]));
  const token = /[\w.~-]+\.(?:m?js|css)\b/g;
  const reached = new Set();
  const queue = [];
  const visit = (text) => {
    for (const name of text.match(token) || []) {
      const f = byName.get(name);
      if (f && !reached.has(f)) {
        reached.add(f);
        queue.push(f);
      }
    }
  };
  for (const page of pages) visit(readFileSync(page, 'utf8'));
  while (queue.length) visit(readFileSync(queue.pop(), 'utf8'));
  const gone = code.filter((f) => !reached.has(f));
  for (const f of gone) rmSync(f);
  return gone.length;
}

export default function publicEdition({ enabled }) {
  return {
    name: 'thorp-public-edition',
    hooks: {
      'astro:server:setup': ({ server, logger }) => {
        if (!enabled) return;
        logger.info('public edition: Demiton and the settings answer 404');
        server.middlewares.use((req, res, next) => {
          const path = (req.url || '/').split('?')[0];
          if ((req.method === 'GET' || req.method === 'HEAD') && isPrivatePath(path)) {
            res.statusCode = 404;
            res.setHeader('content-type', 'text/plain; charset=utf-8');
            res.end('not in the public edition');
            return;
          }
          next();
        });
      },
      'astro:build:done': ({ dir, logger }) => {
        if (!enabled) return;
        const root = fileURLToPath(dir);
        const html = walk(root).filter((f) => f.endsWith('.html'));
        const drop = html.filter((f) => isPrivatePath(routeOf(root, f)));
        for (const f of drop) rmSync(f);
        removeEmptyDirs(root);
        const kept = html.filter((f) => !drop.includes(f));
        const chunks = pruneUnreachable(root, kept);
        logger.info(`public edition: removed ${drop.length} private pages and ${chunks} unreachable scripts; ${kept.length} pages kept`);
        // a link a kept page renders into a private address would be a 404 on the public site
        const leaks = new Map();
        for (const f of kept) {
          for (const m of readFileSync(f, 'utf8').matchAll(/href="(\/[^"#?]*)/g)) {
            if (isPrivatePath(m[1])) leaks.set(m[1], routeOf(root, f));
          }
        }
        for (const [href, page] of leaks) logger.warn(`public edition: ${page} links to ${href}, which this edition leaves out`);
      },
    },
  };
}
