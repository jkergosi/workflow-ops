import path from "path"
import { defineConfig, type UserConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    strictPort: true,
    host: true,
    proxy: {
      '/api': {
        target: 'http://localhost:4000',
        changeOrigin: true,
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    globals: true,
    environment: 'happy-dom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    // Threads pool can OOM in this repo even with maxWorkers=1 due to the per-worker heap cap.
    // Forks pool is heavier but more stable for the full UI suite.
    pool: 'forks',
    maxWorkers: 1,
    poolOptions: {
      forks: {
        execArgv: ['--max-old-space-size=8192'],
      },
    },
    env: {
      VITE_API_BASE_URL: 'http://localhost:3000/api/v1',
      VITE_SUPABASE_URL: 'https://xjunfyugpbyjslqkzlwn.supabase.co',
      VITE_SUPABASE_ANON_KEY: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhqdW5meXVncGJ5anNscWt6bHduIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjIyNTA1NDAsImV4cCI6MjA3NzgyNjU0MH0.DrVdRVzzctWqL6ATsEIeH_U3u2Y-PowbPt-ZWApD7kg',
    },
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/test/**',
        'src/**/*.d.ts',
        'src/main.tsx',
        'src/vite-env.d.ts',
      ],
    },
  },
} as UserConfig & { test: unknown })
