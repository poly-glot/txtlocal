export const POLL_MS = 5_000;

export interface Selection {
  kind: "new" | "thread";
  peer: string;
}
