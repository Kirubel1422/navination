"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useSyncExternalStore } from "react";

import type { Locale } from "@/lib/api/types";
import { dictionaries, type MessageKey } from "./dictionaries";

/** Only the (non-sensitive) language preference is kept in localStorage. */
export const LOCALE_STORAGE_KEY = "navination.locale";
const listeners = new Set<() => void>();

function readLocale(): Locale {
  try {
    return window.localStorage.getItem(LOCALE_STORAGE_KEY) === "ar" ? "ar" : "en";
  } catch {
    return "en";
  }
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

export function writeLocale(locale: Locale): void {
  try {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  } catch {
    // Storage may be unavailable (private mode); the in-memory change still applies below.
  }
  memoryLocale = locale;
  listeners.forEach((listener) => listener());
}

let memoryLocale: Locale | null = null;

export type Translate = (key: MessageKey, params?: Record<string, string | number>) => string;

export function translate(locale: Locale, key: MessageKey, params?: Record<string, string | number>): string {
  let text: string = dictionaries[locale][key] ?? dictionaries.en[key] ?? key;
  if (params) {
    for (const [name, value] of Object.entries(params)) {
      text = text.replaceAll(`{${name}}`, String(value));
    }
  }
  return text;
}

interface LocaleContextValue {
  locale: Locale;
  dir: "ltr" | "rtl";
  setLocale: (locale: Locale) => void;
  t: Translate;
}

const LocaleContext = createContext<LocaleContextValue | null>(null);

export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const locale = useSyncExternalStore(
    subscribe,
    () => memoryLocale ?? readLocale(),
    () => "en" as Locale,
  );
  const dir = locale === "ar" ? "rtl" : "ltr";

  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dir = dir;
  }, [locale, dir]);

  const setLocale = useCallback((next: Locale) => writeLocale(next), []);
  const t = useCallback<Translate>((key, params) => translate(locale, key, params), [locale]);
  const value = useMemo(() => ({ locale, dir, setLocale, t }) as const, [locale, dir, setLocale, t]);
  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale(): LocaleContextValue {
  const value = useContext(LocaleContext);
  if (!value) throw new Error("useLocale must be used inside LocaleProvider");
  return value;
}

/** Runs before first paint so lang/dir are right on hard loads (see Next.js flash guide). */
export const localeBootScript = `try{var l=localStorage.getItem("${LOCALE_STORAGE_KEY}")==="ar"?"ar":"en";document.documentElement.lang=l;document.documentElement.dir=l==="ar"?"rtl":"ltr";}catch(e){}`;
