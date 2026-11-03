import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.js',
    css: false,
    exclude: ['**/node_modules/**', 'tests-node/**'], // tests-node/ uses Node's own test runner (npm run test:integration)
  },
})
