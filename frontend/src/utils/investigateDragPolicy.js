export function createDragTracker(thresholdPx = 4) {
  let startX = 0
  let startY = 0
  let mode = 'idle'
  return {
    start(x, y) {
      startX = x
      startY = y
      mode = 'pending'
    },
    move(x, y) {
      if (mode === 'idle') return 'idle'
      if (mode === 'drag') return 'drag'
      if (Math.hypot(x - startX, y - startY) >= thresholdPx) {
        mode = 'drag'
        return 'drag'
      }
      return 'pending'
    },
    end() {
      const result = mode === 'drag' ? 'drag' : (mode === 'pending' ? 'click' : 'idle')
      mode = 'idle'
      return result
    },
    mode() {
      return mode
    },
  }
}
