export function activityRowShowsPayloadActions(row) {
  if (!row) return false
  if (row.payload_actionable != null) return Boolean(row.payload_actionable)
  return Boolean(row.has_payload)
}
