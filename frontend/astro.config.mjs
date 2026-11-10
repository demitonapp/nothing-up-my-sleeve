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
