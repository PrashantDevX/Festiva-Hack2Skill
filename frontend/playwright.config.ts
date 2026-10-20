import { defineConfig } from '@playwright/test'
import { existsSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const workspaceRoot = fileURLToPath(new URL('../', import.meta.url))
const testDatabase = path.join(os.tmpdir(), 'festiva-e2e-test.db')
const venvPython =
  process.platform === 'win32'
    ? path.join(workspaceRoot, '.venv', 'Scripts', 'python.exe')
    : path.join(workspaceRoot, '.venv', 'bin', 'python')
const pythonCommand =
  process.env.FESTIVA_PYTHON ?? (existsSync(venvPython) ? venvPython : 'python')

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:5173',
    channel: 'msedge',
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: `"${pythonCommand}" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000`,
      cwd: workspaceRoot,
      url: 'http://127.0.0.1:8000/api/health',
      env: {
        ...process.env,
        FESTIVA_AI_MODE: 'demo',
        FESTIVA_DB_PATH: testDatabase,
      },
      reuseExistingServer: false,
      timeout: 30000,
    },
    {
      command: 'npm --prefix frontend run dev -- --host 127.0.0.1 --strictPort',
      cwd: workspaceRoot,
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: false,
      timeout: 30000,
    },
  ],
})
