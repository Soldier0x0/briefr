import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import {
  dailyBriefTestToast,
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

  it('SigmaHQ catalog label is used in started toast', () => {
    const msg = schedulerJobStarted('sigmahq_index_sync', 'operator')
    assert.match(msg, /SigmaHQ Detection Rule Index Sync/)
    assert.doesNotMatch(msg, /sigmahq_index_sync/)
  })

  it('pause copy uses human name', () => {
    assert.match(schedulerJobPaused('epss_score_sync'), /paused$/)
  })

  it('uses a warning with the reason when a daily brief test is skipped', () => {
    assert.deepEqual(
      dailyBriefTestToast({ status: 'skipped', reason: 'no_subscribers' }),
      {
        message: 'Daily brief test skipped — no subscribers',
        variant: 'warning',
      },
    )
  })
})
