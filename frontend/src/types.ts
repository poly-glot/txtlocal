export type Fetch = typeof fetch;

export interface Notice {
  message: string;
  tone: "error" | "success";
}

export type Result<T> = { data: T; status: "OK" } | { message: string; status: "ERROR" };
