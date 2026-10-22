export function paginateDraws(history, { limit = 12, offset = 0, issue = "" } = {}) {
  const normalizedIssue = String(issue || "").trim();
  const filtered = history
    .slice()
    .reverse()
    .filter((row) => !normalizedIssue || row.issue.includes(normalizedIssue));
  return {
    items: filtered.slice(offset, offset + limit),
    total: filtered.length,
    limit,
    offset,
    issue: normalizedIssue,
  };
}
