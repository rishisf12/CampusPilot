import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/attendance': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/timetable': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/schedule': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/rooms': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/exam': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/profile': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})