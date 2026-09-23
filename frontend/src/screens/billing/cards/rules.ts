export function cardExpiry(expMonth: number, expYear: number): string {
  return `${String(expMonth).padStart(2, "0")}/${String(expYear % 100).padStart(2, "0")}`;
}
