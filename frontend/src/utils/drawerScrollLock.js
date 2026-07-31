/**
 * Drawer wheel trap: block scroll chaining to the feed behind the drawer,
 * but allow nested overflow containers (e.g. CodePanel) to scroll normally.
 */
export function handleDrawerWheel(event, panel) {
  if (!panel) {
    event.preventDefault()
    return
  }

  let node = event.target
  while (node && node !== panel) {
    const { overflowY } = window.getComputedStyle(node)
    if (
      (overflowY === 'auto' || overflowY === 'scroll')
      && node.scrollHeight > node.clientHeight + 1
    ) {
      const { scrollTop, scrollHeight, clientHeight } = node
      const scrollingUp = event.deltaY < 0
      const scrollingDown = event.deltaY > 0
      if (
        (scrollingUp && scrollTop > 0)
        || (scrollingDown && scrollTop + clientHeight < scrollHeight - 1)
      ) {
        return
      }
    }
    node = node.parentElement
  }

  const { scrollTop, scrollHeight, clientHeight } = panel
  const atTop = scrollTop <= 0 && event.deltaY < 0
  const atBottom = scrollTop + clientHeight >= scrollHeight - 1 && event.deltaY > 0
  if (atTop || atBottom) {
    event.preventDefault()
    event.stopPropagation()
  }
}
