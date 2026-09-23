export function saveCsv(csv: string, filename: string): void {
  const anchor = document.createElement("a");
  anchor.download = filename;
  anchor.href = `data:text/csv;charset=utf-8,${encodeURIComponent(csv)}`;
  anchor.click();
}
