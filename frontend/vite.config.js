import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * Dev server proxy.
 *
 * Every backend prefix is forwarded to the FastAPI server so the frontend can
 * use same-origin paths (`/auth`, `/profile`, `/exam`, ...) and stay free of
 * CORS issues. Keep the target port in sync with the uvicorn command.
 */
const BACKEND = 'http://localhost:8002'

const proxied = [
  '/api',
  '/auth',
  '/profile',
  '/timetable',
  '/schedule',
  '/rooms',
  '/exam',
  '/attendance',
  '/ocr',
  '/health',
]

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      proxied.map((path) => [path, { target: BACKEND, changeOrigin: true }])
    ),
  },
})