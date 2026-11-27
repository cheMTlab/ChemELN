import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'
import { VitePWA } from 'vite-plugin-pwa'

// Keep the browser's Host header (changeOrigin: false) so Django sees the same origin as the
// page, just like behind Caddy in production. Otherwise CSRF origin checks reject logins.
const apiTarget = { target: process.env.VITE_API_PROXY ?? 'http://localhost:8000', changeOrigin: false }

export default defineConfig({
  plugins: [
    react(),
    // Installable on phones/tablets via "Add to Home Screen". Offline data sync arrives in M2.
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'CheMTlab',
        short_name: 'CheMTlab',
        description: 'Open-source ELN and chemical inventory',
        theme_color: '#1c7ed6',
        background_color: '#ffffff',
        display: 'standalone',
        start_url: '/',
        icons: [{ src: '/icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' }],
      },
      workbox: {
        // Never cache API responses or auth endpoints in the service worker.
        navigateFallbackDenylist: [/^\/api\//, /^\/_allauth\//, /^\/admin\//],
        // The Ketcher editor (~21 MB, includes the Indigo WASM engine) is loaded on demand, not precached.
        globIgnores: ['**/ketcher-*.js', '**/ketcher-*.css'],
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: {
      '/api': apiTarget,
      '/_allauth': apiTarget,
      '/admin': apiTarget,
      '/static': apiTarget,
    },
  },
  test: {
    environment: 'jsdom',
  },
})
