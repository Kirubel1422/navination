export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1"
).replace(/\/$/, "");

export const API_MODE: "live" | "mock" =
  process.env.NEXT_PUBLIC_API_MODE === "mock" ? "mock" : "live";

export const REQUEST_TIMEOUT_MS = 20_000;
