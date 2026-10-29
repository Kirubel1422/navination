import { API_BASE_URL, REQUEST_TIMEOUT_MS } from "@/lib/config";
import type { ErrorEnvelope } from "./types";

/** Client-side failure codes in addition to the API's stable error codes. */
export type ClientErrorCode = "NETWORK_ERROR" | "TIMEOUT" | "ABORTED" | "BAD_RESPONSE";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string | null;
  readonly details: ErrorEnvelope["error"]["details"];

  constructor(
    status: number,
    code: string,
    message: string,
    requestId: string | null = null,
    details: ErrorEnvelope["error"]["details"] = [],
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.details = details;
  }

  get isSessionProblem(): boolean {
    return this.status === 401;
  }
}

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export interface RequestOptions {
  method?: Method;
  body?: unknown;
  token?: string | null;
  signal?: AbortSignal;
  timeoutMs?: number;
}

type UnauthorizedListener = (error: ApiError) => void;
const unauthorizedListeners = new Set<UnauthorizedListener>();

/** The session layer subscribes so any 401 moves the app into an explicit expired state. */
export function onUnauthorized(listener: UnauthorizedListener): () => void {
  unauthorizedListeners.add(listener);
  return () => unauthorizedListeners.delete(listener);
}

function isEnvelope(value: unknown): value is ErrorEnvelope {
  return (
    typeof value === "object" &&
    value !== null &&
    "error" in value &&
    typeof (value as ErrorEnvelope).error?.code === "string"
  );
}

/**
 * The single typed request helper. Handles authorization, JSON errors, 204 responses,
 * caller aborts and timeouts. It never retries: callers decide whether a retry is safe.
 */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, token, signal, timeoutMs = REQUEST_TIMEOUT_MS } = options;
  const timeout = AbortSignal.timeout(timeoutMs);
  const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: combined,
      cache: "no-store",
      credentials: "omit",
    });
  } catch (error) {
    if (timeout.aborted) {
      throw new ApiError(0, "TIMEOUT", "The request took too long.");
    }
    if (signal?.aborted) {
      throw new ApiError(0, "ABORTED", "The request was cancelled.");
    }
    throw new ApiError(0, "NETWORK_ERROR", error instanceof Error ? error.message : "Network error");
  }

  if (response.status === 204) {
    return undefined as T;
  }

  let payload: unknown = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      throw new ApiError(response.status, "BAD_RESPONSE", "The server sent an unreadable response.");
    }
  }

  if (!response.ok) {
    const error = isEnvelope(payload)
      ? new ApiError(
          response.status,
          payload.error.code,
          payload.error.message,
          payload.error.request_id,
          payload.error.details,
        )
      : new ApiError(
          response.status,
          "BAD_RESPONSE",
          `Request failed with status ${response.status}.`,
          response.headers.get("x-request-id"),
        );
    if (response.status === 401) {
      unauthorizedListeners.forEach((listener) => listener(error));
    }
    throw error;
  }
  return payload as T;
}
