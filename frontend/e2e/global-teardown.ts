import { rmSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'

export default function globalTeardown() {
  const database = path.join(os.tmpdir(), 'festiva-e2e-test.db')
  for (const suffix of ['', '-wal', '-shm']) {
    rmSync(`${database}${suffix}`, { force: true })
  }
}
