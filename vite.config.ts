import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  server: {
    host: '0.0.0.0', // Allow connections from outside the container
    port: 5173,      // Explicitly set port
    strictPort: true, // Fail if port is not available
    watch: {
      usePolling: true, // Enable polling for hot reload in Docker
      interval: 1000,   // Check for changes every second
    },
    proxy: {
      '/api': {
        target: 'http://localhost:3000',
        changeOrigin: true
      },
      '/socket.io': {
        target: 'http://localhost:3000',
        ws: true
      },
      '/assets': {
        target: 'http://localhost:3000',
        changeOrigin: true
      }
    }
  }
})