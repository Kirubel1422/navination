import type { Discovery, Locale } from "@/lib/api/types";
import { readStored, removeStored, useStored, writeStored } from "@/lib/session/storage";

export interface StoredDiscovery {
  sessionId: string;
  locale: Locale;
  discovery: Discovery;
  selected: string[];
}

export function loadDiscovery(sessionId: string): StoredDiscovery | null {
  const stored = readStored<StoredDiscovery>("discovery");
  return stored && stored.sessionId === sessionId ? stored : null;
}

export function saveDiscovery(value: StoredDiscovery): void {
  writeStored("discovery", value);
}

/** Keeps the previous result set so the UI can explain what a profile change altered. */
export function savePreviousDiscovery(value: StoredDiscovery | null): void {
  if (value) writeStored("previousDiscovery", value);
  else removeStored("previousDiscovery");
}

export function loadPreviousDiscovery(sessionId: string): StoredDiscovery | null {
  const stored = readStored<StoredDiscovery>("previousDiscovery");
  return stored && stored.sessionId === sessionId ? stored : null;
}

export function defaultSelection(discovery: Discovery): string[] {
  return discovery.results.filter((c) => c.relevance !== "criterion_mismatch").map((c) => c.service.id);
}

/** Live view of the stored discovery for this session (see useStored for why it must be live). */
export function useStoredDiscovery(sessionId: string): StoredDiscovery | null {
  const stored = useStored<StoredDiscovery>("discovery");
  return stored && stored.sessionId === sessionId ? stored : null;
}

export function usePreviousDiscovery(sessionId: string): StoredDiscovery | null {
  const stored = useStored<StoredDiscovery>("previousDiscovery");
  return stored && stored.sessionId === sessionId ? stored : null;
}
