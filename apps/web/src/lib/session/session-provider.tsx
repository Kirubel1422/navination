"use client";

import { type QueryClient, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import { ApiError, onUnauthorized } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import type { Locale, Session } from "@/lib/api/types";
import { useLocale } from "@/lib/i18n/locale";
import { clearPrivateState, readStored, writeStored } from "./storage";

export type SessionState =
  | { status: "loading" }
  | { status: "ready"; token: string; session: Session }
  | { status: "expired" }
  | { status: "cleared" }
  | { status: "error"; error: ApiError };

interface Bootstrapped {
  token: string;
  session: Session;
}

/*
 * Module-level promise so React Strict Mode's double effects (and concurrent mounts) share one
 * bootstrap and never create two guest sessions.
 */
let bootstrapPromise: Promise<Bootstrapped> | null = null;

function bootstrap(locale: Locale): Promise<Bootstrapped> {
  if (!bootstrapPromise) {
    bootstrapPromise = (async () => {
      const stored = readStored<string>("token");
      if (stored) {
        const session = await api.getSession({ token: stored });
        return { token: stored, session };
      }
      const created = await api.createSession(locale);
      writeStored("token", created.access_token);
      return { token: created.access_token, session: created.session };
    })();
    bootstrapPromise.catch(() => {
      bootstrapPromise = null;
    });
  }
  return bootstrapPromise;
}

interface SessionContextValue {
  state: SessionState;
  setSession: (session: Session) => void;
  startNewSession: () => Promise<void>;
  clearSession: () => Promise<void>;
  retryBootstrap: () => void;
}

const SessionContext = createContext<SessionContextValue | null>(null);

/** Public open data (never tied to a session) stays cached when the guest session ends. */
const PUBLIC_QUERY_ROOTS = new Set(["open-data", "open-data-search", "navigation-gaps"]);

function clearPrivateQueries(queryClient: QueryClient): void {
  queryClient.removeQueries({ predicate: (query) => !PUBLIC_QUERY_ROOTS.has(String(query.queryKey[0])) });
}

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const { locale } = useLocale();
  const queryClient = useQueryClient();
  const [state, setState] = useState<SessionState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  const localeRef = useRef(locale);
  useEffect(() => {
    localeRef.current = locale;
  }, [locale]);

  const expire = useCallback(() => {
    bootstrapPromise = null;
    clearPrivateState();
    clearPrivateQueries(queryClient);
    setState((current) => (current.status === "cleared" ? current : { status: "expired" }));
  }, [queryClient]);

  useEffect(() => onUnauthorized(() => expire()), [expire]);

  useEffect(() => {
    let active = true;
    bootstrap(localeRef.current)
      .then((result) => {
        if (active) setState({ status: "ready", ...result });
      })
      .catch((error: unknown) => {
        if (!active) return;
        if (error instanceof ApiError && error.status === 401) {
          expire();
        } else {
          setState({
            status: "error",
            error: error instanceof ApiError ? error : new ApiError(0, "NETWORK_ERROR", String(error)),
          });
        }
      });
    return () => {
      active = false;
    };
  }, [attempt, expire]);

  // Keep the backend locale in step with the UI. Locale changes never alter context_revision.
  useEffect(() => {
    if (state.status !== "ready" || state.session.locale === locale) return;
    const { token } = state;
    api
      .updateLocale({ token }, locale)
      .then((session) => setState((current) => (current.status === "ready" ? { ...current, session } : current)))
      .catch(() => {
        // A failed locale sync leaves content in the previous language; the next request retries.
      });
  }, [state, locale]);

  const setSession = useCallback((session: Session) => {
    setState((current) => (current.status === "ready" ? { ...current, session } : current));
  }, []);

  const startNewSession = useCallback(async () => {
    bootstrapPromise = null;
    clearPrivateState();
    clearPrivateQueries(queryClient);
    setState({ status: "loading" });
    setAttempt((n) => n + 1);
  }, [queryClient]);

  const clearSession = useCallback(async () => {
    if (state.status !== "ready") return;
    await api.deleteSession({ token: state.token });
    bootstrapPromise = null;
    clearPrivateState();
    clearPrivateQueries(queryClient);
    setState({ status: "cleared" });
  }, [state, queryClient]);

  const retryBootstrap = useCallback(() => {
    bootstrapPromise = null;
    setState({ status: "loading" });
    setAttempt((n) => n + 1);
  }, []);

  const value = useMemo(
    () => ({ state, setSession, startNewSession, clearSession, retryBootstrap }),
    [state, setSession, startNewSession, clearSession, retryBootstrap],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside SessionProvider");
  return value;
}

/** For components rendered only when the session is ready. */
export function useReadySession(): { token: string; session: Session } {
  const { state } = useSession();
  if (state.status !== "ready") throw new Error("Session is not ready");
  return { token: state.token, session: state.session };
}
