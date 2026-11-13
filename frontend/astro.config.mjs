// The dashboard (frontend/) is served by `pnpm dev` on :4321, which forwards /api to a running `thorp dash`.
// `thorp dash` (:8787) serves the JSON API only, no page.
// React and Tailwind are here for shadcn/ui (src/components/ui, UI.md "Components").
import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
import tailwindcss from '@tailwindcss/vite';
import publicEdition from './integrations/public-edition.mjs';

// The public edition (13 November, src/lib/edition.ts): `PUBLIC_EDITION=1 pnpm build` builds the public site,
// without Demiton or the settings, into frontend/dist-public, so it never overwrites the dashboard's own build.
const PUBLIC = process.env.PUBLIC_EDITION === '1';

// A branch's address (/library/ogden) is data, not a fixed route: `thorp dash` already serves the
// Library's shell for any branch in production, and this gives the dev server the same fallback.
// The static build still writes a page per default branch (pages/library/[...path].astro), and the
// island reads the address, so the shell does not need to know which key was asked for.
const libraryBranchShell = {
  name: 'library-branch-shell',
  configureServer(server) {
    server.middlewares.use((req, _res, next) => {
      if (req.url && (req.method === 'GET' || req.method === 'HEAD') && /^\/library\/[^/?#]+\/?(?:\?.*)?$/.test(req.url)) {
        req.url = '/library';
      }
      next();
    });
  },
};

export default defineConfig({
  outDir: PUBLIC ? './dist-public' : '../backend/thorp/dash/static',
  build: { assets: 'assets' },
  devToolbar: { enabled: false },
  server: { port: 4321 },
  integrations: [react(), publicEdition({ enabled: PUBLIC })],
  // The Liberty Machine lives under Demiton (12 November, Justin: "for this url .../liberty-machine it
  // should be behind the demiton orbital url structure") and was called VSM before that: every old
  // address 301s into the orbital's tree. S1's page is 'operations'.
  // Every one of them lands in Demiton, so the public edition has none.
  redirects: PUBLIC ? {} : {
    '/liberty-machine': '/orbitals/demiton/liberty-machine',
    '/liberty-machine/s1': '/orbitals/demiton/liberty-machine/operations',
    '/liberty-machine/s2': '/orbitals/demiton/liberty-machine/s2',
    '/liberty-machine/s3': '/orbitals/demiton/liberty-machine/s3',
    '/liberty-machine/s4': '/orbitals/demiton/liberty-machine/s4',
    '/liberty-machine/s5': '/orbitals/demiton/liberty-machine/s5',
    '/liberty-machine/control': '/orbitals/demiton/liberty-machine/s3',
    '/liberty-machine/acquisition': '/orbitals/demiton/liberty-machine/operations',
    '/liberty-machine/operations': '/orbitals/demiton/liberty-machine/operations',
    '/liberty-machine/operations/browser': '/orbitals/demiton/liberty-machine/operations/browser',
    '/liberty-machine/operations/email': '/orbitals/demiton/liberty-machine/operations/email',
    '/liberty-machine/operations/phone': '/orbitals/demiton/liberty-machine/operations/phone',
    '/vsm': '/orbitals/demiton/liberty-machine',
    '/vsm/s1': '/orbitals/demiton/liberty-machine/operations',
    '/vsm/s2': '/orbitals/demiton/liberty-machine/s2',
    '/vsm/s3': '/orbitals/demiton/liberty-machine/s3',
    '/vsm/s4': '/orbitals/demiton/liberty-machine/s4',
    '/vsm/s5': '/orbitals/demiton/liberty-machine/s5',
    '/vsm/control': '/orbitals/demiton/liberty-machine/s3',
    '/vsm/acquisition': '/orbitals/demiton/liberty-machine/operations',
    '/vsm/s1/browser': '/orbitals/demiton/liberty-machine/operations/browser',
    '/vsm/operations': '/orbitals/demiton/liberty-machine/operations',
    '/governance': '/orbitals/demiton/liberty-machine',
    '/governance/s1': '/orbitals/demiton/liberty-machine/operations',
    '/governance/s2': '/orbitals/demiton/liberty-machine/s2',
    '/governance/s3': '/orbitals/demiton/liberty-machine/s3',
    '/governance/s4': '/orbitals/demiton/liberty-machine/s4',
    '/governance/s5': '/orbitals/demiton/liberty-machine/s5',
    '/governance/control': '/orbitals/demiton/liberty-machine/s3',
    '/governance/acquisition': '/orbitals/demiton/liberty-machine/operations',
  },
  vite: {
    plugins: [libraryBranchShell, tailwindcss()],
    // one value for the server render and the islands alike ('1' or ''), read through src/lib/edition.ts
    define: { 'import.meta.env.PUBLIC_EDITION': JSON.stringify(PUBLIC ? '1' : '') },
    // pre-bundled at startup, so a newly imported one never re-optimises under an open tab
    // (the browser then asks for the old bundle: "504 Outdated Optimize Dep")
    optimizeDeps: {
      include: ['react', 'react-dom', 'react-dom/client', 'radix-ui',
                'class-variance-authority', 'clsx', 'tailwind-merge', 'lucide-react',
                // the chart modules are imported on demand (lib/echarts), so without these the first
                // chart in an open tab re-optimises the deps and the import 504s: a blank chart
                'echarts/core', 'echarts/charts', 'echarts/components', 'echarts/renderers'],
    },
    server: { proxy: { '/api': 'http://localhost:8787' } },
    build: { chunkSizeWarningLimit: 5000 },  // ECharts is split into several large modules, on purpose
  },
});
