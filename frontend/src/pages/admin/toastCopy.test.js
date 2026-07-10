import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import {
  schedulerJobManualRun,
  schedulerJobPaused,
  schedulerJobRetry,
  schedulerJobStarted,
} from './toastCopy.js'

describe('toastCopy', () => {
  it('uses catalog labels not raw job ids', () => {
    const msg = schedulerJobStarted('nvd_incremental_sync', 'operator')
    assert.match(msg, /NVD Incremental Sync/)
    assert.doesNotMatch(msg, /nvd_incremental_sync/)
  })

  it('retry copy includes Retry started prefix', () => {
    assert.match(schedulerJobRetry('kev_metadata_sync', 'operator'), /^Retry started —/)
  })

  it('manual run copy includes Manual run started prefix', () => {
    assert.match(schedulerJobManualRun('epss_score_sync'), /^Manual run started —/)
  })

  it('pause copy uses human name', () => {
    assert.match(schedulerJobPaused('epss_score_sync'), /paused$/)
  })
})
