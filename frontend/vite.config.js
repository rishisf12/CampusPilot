import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * Dev server on 5173 with every backend prefix proxied to FastAPI on 8001, so
 * the app can use same-origin paths and stay free of CORS problems.
 */
const BACKEND = 'http://localhost:8001'

const proxied = [
  '/api',
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
]

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: Object.fromEntries(
      proxied.map((path) => [path, { target: BACKEND, changeOrigin: true }]),
    ),
  },
})