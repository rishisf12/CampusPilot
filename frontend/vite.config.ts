import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

/**
 * Dev server on 5173 with backend requests proxied to FastAPI on 8001, so the
 * app can use same-origin paths and stay free of CORS problems.
 */
const BACKEND = 'http://localhost:8000';

/**
 * Backend path prefixes proxied to FastAPI.
 *
 * This list must cover every router the backend mounts. It used to drift:
 * `/monitoring` and `/collect` were added to the backend and to
 * `frontend/nginx.conf`, but not here, so monitoring requests worked in the
 * container and 404'd under `npm run dev` - the worst possible failure,
 * because the environment nobody deploys is the one that looked broken.
 *
 * Two things stop that recurring:
 *
 * 1. `nginx.conf` no longer keeps a copy of this list. It uses
 *    `try_files $uri $uri/ @backend`, so a new backend router needs no change
 *    there at all. This file is now the only list.
 * 2. `backend/backend/tests/test_proxy_coverage.py` parses both this file and
 *    the FastAPI routers and fails if a prefix is missing from either, or if
 *    this file lists a prefix the backend does not serve. A hand-written list
 *    with an automated consistency check is easier to read than a clever regex
 *    and far easier to trust.
 */
const proxied = [
  '/auth',
  '/profile',
  '/schedule',
  '/timetable',
  '/rooms',
  '/attendance',
  '/exam',
  '/health',
  '/ocr',
  '/feedback',
  '/teams',
  '/hackathons',
  '/monitoring',
  '/collect',
  '/metrics',
];

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: Object.fromEntries(proxied.map(p => [p, { target: BACKEND, changeOrigin: true }])),
  },
});
