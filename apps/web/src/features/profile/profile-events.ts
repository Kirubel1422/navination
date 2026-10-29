const EVENT = "navination:open-profile";

/** Lets any component (for example a "missing information" hint) open the profile sheet. */
export function openProfileSheet(): void {
  window.dispatchEvent(new CustomEvent(EVENT));
}

export function onOpenProfileSheet(handler: () => void): () => void {
  window.addEventListener(EVENT, handler);
  return () => window.removeEventListener(EVENT, handler);
}
