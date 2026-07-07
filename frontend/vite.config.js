import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const writeExcelSyncRoot = path.resolve(__dirname, 'node_modules/write-excel-file/modules/export')

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // Public package exports only expose async browser build (fflate Web Workers).
      'write-excel-file/modules/export/writeXlsxFileUniversal.js': path.join(writeExcelSyncRoot, 'writeXlsxFileUniversal.js'),
      'write-excel-file/modules/export/convertFileContentToUint8ArrayUniversal.js': path.join(writeExcelSyncRoot, 'convertFileContentToUint8ArrayUniversal.js'),
    },
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 5173,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: process.env.PLAYWRIGHT_BACKEND_URL || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
