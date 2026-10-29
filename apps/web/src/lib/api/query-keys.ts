import type { Locale } from "./types";

/**
 * Query keys always include session identity and, for localized content, the locale the server
 * has confirmed for the session (not just the UI toggle), so a refetch never races the locale sync.
 */
export const queryKeys = {
  session: (sessionId: string) => ["session", sessionId] as const,
  service: (sessionId: string, locale: Locale, revision: number, serviceId: string) =>
    ["service", sessionId, locale, revision, serviceId] as const,
  journey: (sessionId: string, locale: Locale, journeyId: string) =>
    ["journey", sessionId, locale, journeyId] as const,
  messages: (sessionId: string, locale: Locale, journeyId: string) =>
    ["messages", sessionId, locale, journeyId] as const,
  health: () => ["health"] as const,
};
