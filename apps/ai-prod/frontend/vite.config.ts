import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const runtimeOrigin = env.VITE_DEV_RUNTIME_ORIGIN || 'http://127.0.0.1:26004'
  const internalOrigin = env.VITE_DEV_INTERNAL_ORIGIN || 'http://127.0.0.1:26014'

  return {
    plugins: [react()],
    resolve: {
      dedupe: ['react', 'react/jsx-runtime'],
    },
    server: {
      proxy: {
        '/api/v1': runtimeOrigin,
        '/internal': internalOrigin,
      },
    },
  }
})
