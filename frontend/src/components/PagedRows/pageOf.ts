interface RowsPage<Row> {
  nextCursor: string | null;
  rows: readonly Row[];
}

export function pageOf<Row>(
  rows: readonly Row[],
  cursor: string | undefined,
  limit: number,
): RowsPage<Row> {
  const start = Number(cursor ?? 0);
  const end = start + limit;

  return { nextCursor: end < rows.length ? String(end) : null, rows: rows.slice(start, end) };
}
