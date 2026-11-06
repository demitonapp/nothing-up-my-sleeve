// The dashboard builds to ../static, which `thorp dash` (server.py) serves beside its JSON API.
// `pnpm dev` serves the page with hot reload on :4321 and forwards /api to a running `thorp dash`.
import { defineConfig } from 'astro/config';

export default defineConfig({
  outDir: '../static',
  build: { assets: 'assets' },
  devToolbar: { enabled: false },
  server: { port: 4321 },
  vite: {
    server: { proxy: { '/api': 'http://localhost:8787' } },
    build: { chunkSizeWarningLimit: 5000 },  // Plotly is one large module, on purpose
  },
});
