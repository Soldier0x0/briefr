export function outboundJobsEmptyMessage({ enabled }) {
  if (!enabled) {
    return 'Durable outbound jobs are off (PROCRASTINATE_ENABLED=0). Enable and restart to use this queue.'
  }
  return 'No durable jobs yet.'
}
