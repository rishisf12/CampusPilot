import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

/**
 * Dev server on 5173 with backend requests proxied to FastAPI on 8000, so the
 * app can use same-origin paths and stay free of CORS problems.
 *
 * The literal 127.0.0.1 is load-bearing, not a style choice. `localhost`
 * resolves to `::1` first on Windows (and on any host with IPv6 enabled), but
 * `uvicorn` binds IPv4-only unless you pass `--host 0.0.0.0`. Node's proxy then
 * dials `::1`, gets ECONNREFUSED, and every single proxied path returns 500
 * with an empty body - while the backend is perfectly healthy and answers 200
 * on 127.0.0.1. That is the "Backend offline" banner in the UI with no useful
 * error anywhere.
 *
 * Override with VITE_DEV_BACKEND if you run the backend somewhere else, e.g.
 * `VITE_DEV_BACKEND=http://localhost:8002` when using the Docker stack. Keep
 * the IP literal in that case too, for the same reason.
 */
const BACKEND = process.env.VITE_DEV_BACKEND || 'http://127.0.0.1:8000';

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
