"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";

const AnnouncerContext = createContext<(message: string) => void>(() => {});

/** A single polite live region so status changes are announced to assistive technology. */
export function AnnouncerProvider({ children }: { children: React.ReactNode }) {
  const [message, setMessage] = useState("");
  const announce = useCallback((text: string) => {
    setMessage("");
    window.setTimeout(() => setMessage(text), 50);
  }, []);
  const value = useMemo(() => announce, [announce]);
  return (
    <AnnouncerContext.Provider value={value}>
      {children}
      <div role="status" aria-live="polite" aria-atomic="true" className="sr-only" data-testid="announcer">
        {message}
      </div>
    </AnnouncerContext.Provider>
  );
}

export function useAnnounce(): (message: string) => void {
  return useContext(AnnouncerContext);
}
