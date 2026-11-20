import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ command }) => ({
  // Production builds are served by Django/WhiteNoise from /static/, so asset
  // URLs must be absolute (/static/assets/...). The dev server keeps '/'.
  base: command === 'build' ? '/static/' : '/',
  plugins: [react(), tailwindcss()],
  server: {
  proxy: {
    '/api': {
      target: 'http://127.0.0.1:8000',
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api/, ''), // Strips /api before sending to Django
    },
      '/media': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
  }
}
}))
