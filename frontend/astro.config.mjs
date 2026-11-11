// The dashboard (frontend/) builds to backend/thorp/dash/static, which `thorp dash` (server.py) serves beside its JSON API.
// `pnpm dev` serves the page with hot reload on :4321 and forwards /api to a running `thorp dash`.
// React and Tailwind are here for shadcn/ui (src/components/ui, UI.md "Components").
import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  outDir: '../backend/thorp/dash/static',
  build: { assets: 'assets' },
  devToolbar: { enabled: false },
  server: { port: 4321 },
  integrations: [react()],
  // the VSM moved to /vsm (11 November, Justin: "the url should be vsm"); the old addresses keep working
  redirects: {
    '/governance': '/vsm',
    '/governance/s1': '/vsm',
    '/governance/s2': '/vsm/s2',
    '/governance/s3': '/vsm/s3',
    '/governance/s4': '/vsm/s4',
    '/governance/s5': '/vsm/s5',
    '/governance/control': '/vsm/s3',
    '/governance/acquisition': '/vsm',
  },
  vite: {
    plugins: [tailwindcss()],
    // pre-bundled at startup, so a newly imported one never re-optimises under an open tab
    // (the browser then asks for the old bundle: "504 Outdated Optimize Dep")
    optimizeDeps: {
      include: ['react', 'react-dom', 'react-dom/client', 'radix-ui',
                'class-variance-authority', 'clsx', 'tailwind-merge', 'lucide-react'],
    },
    server: { proxy: { '/api': 'http://localhost:8787' } },
    build: { chunkSizeWarningLimit: 5000 },  // ECharts is split into several large modules, on purpose
  },
});
