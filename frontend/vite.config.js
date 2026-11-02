import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src')
    }
  },
  server: {
    port: Number(process.env.LEHRJAHRE_WEB_PORT) || 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${process.env.LEHRJAHRE_API_PORT || 5000}`,
        changeOrigin: true
      }
    }
  }
})
