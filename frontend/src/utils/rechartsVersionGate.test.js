import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

function readPackageJson() {
  const pkgPath = path.join(path.dirname(fileURLToPath(import.meta.url)), '../../package.json')
  return JSON.parse(fs.readFileSync(pkgPath, 'utf8'))
}

describe('Recharts v3 gate', () => {
  it('package.json pins recharts 3.x (2.x is deprecated)', () => {
    const pkg = readPackageJson()
    const version = pkg.dependencies?.recharts || ''
    assert.match(version, /^\^?3\./, `expected recharts 3.x, got ${version}`)
  })

  it('chart modules import from recharts and use shared theme helpers', () => {
    const chartFiles = [
      '../pages/admin/shared/opsChartsRecharts.jsx',
      '../components/briefVendorChartRecharts.jsx',
      '../pages/admin/resourcesChartsRecharts.jsx',
    ]
    for (const rel of chartFiles) {
      const src = fs.readFileSync(new URL(rel, import.meta.url), 'utf8')
      assert.match(src, /from 'recharts'/, `${rel} must import from recharts`)
      assert.match(src, /rechartsTheme/, `${rel} must use rechartsTheme helpers`)
    }
  })
})
