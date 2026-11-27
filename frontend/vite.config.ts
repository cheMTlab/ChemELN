/// <reference types="vitest" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

const apiTarget = process.env.VITE_API_PROXY ?? 'http://localhost:8000'

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
