/**
 * Tab-scoped storage for private session state. The bearer token and the last discovery live in
 * sessionStorage (cleared when the tab closes) and never in URLs or localStorage.
 *
 * Views read it through `useStored`, a subscription, never a one-off copy in component state:
 * Next.js (Cache Components) keeps visited pages mounted but hidden, so a copy taken when a page
 * first rendered would go stale when the person searches again elsewhere.
 */
import { useSyncExternalStore } from "react";

const KEYS = {
  token: "navination.token",
  discovery: "navination.discovery",
  previousDiscovery: "navination.previousDiscovery",
  activeJourney: "navination.activeJourney",
  location: "navination.location",
} as const;

type Key = keyof typeof KEYS;

export function readStored<T>(key: Key): T | null {
  try {
    const raw = window.sessionStorage.getItem(KEYS[key]);
    return raw === null ? null : (JSON.parse(raw) as T);
  } catch {
    return null;
  }
}

const listeners = new Set<() => void>();
const notify = () => listeners.forEach((listener) => listener());

export function writeStored(key: Key, value: unknown): void {
  try {
    window.sessionStorage.setItem(KEYS[key], JSON.stringify(value));
  } catch {
    // Without storage the app still works for the current page view.
  }
  notify();
}

export function removeStored(key: Key): void {
  try {
    window.sessionStorage.removeItem(KEYS[key]);
  } catch {
    // ignore
  }
  notify();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

// useSyncExternalStore needs a stable snapshot: re-parse only when the raw string changes.
const snapshots = new Map<Key, { raw: string | null; value: unknown }>();

function snapshot<T>(key: Key): T | null {
  let raw: string | null = null;
  try {
    raw = window.sessionStorage.getItem(KEYS[key]);
  } catch {
    return null;
  }
  const cached = snapshots.get(key);
  if (cached && cached.raw === raw) return cached.value as T | null;
  let value: T | null = null;
  try {
    value = raw === null ? null : (JSON.parse(raw) as T);
  } catch {
    value = null;
  }
  snapshots.set(key, { raw, value });
  return value;
}

/** The current stored value, re-rendering whenever any view writes or clears it. */
export function useStored<T>(key: Key): T | null {
  return useSyncExternalStore(subscribe, () => snapshot<T>(key), () => null);
}

export function clearPrivateState(): void {
  (Object.keys(KEYS) as Key[]).forEach(removeStored);
}
