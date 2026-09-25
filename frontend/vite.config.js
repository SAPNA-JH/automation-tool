import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// The SPA talks to the backend via absolute URLs (VITE_API_URL), so no dev proxy is
// needed. Vite's built-in SPA history fallback then serves index.html for client routes
// like /posts and /templates on hard-refresh.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
