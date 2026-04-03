import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendOrigin = env.VITE_DEV_BACKEND_ORIGIN || 'http://127.0.0.1:26004'

  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api/v1': backendOrigin,
        '/internal': backendOrigin,
      },
    },
  }
})
