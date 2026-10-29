"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

import type { Locale } from "@/lib/api/types";

/** The browser's speech recognition (Chrome, Edge, Safari). Not typed in lib.dom yet. */
interface Recognition {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  maxAlternatives: number;
  onresult: ((event: { resultIndex: number; results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }> }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}
type RecognitionCtor = new () => Recognition;

function recognitionCtor(): RecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

const noop = () => () => {};

export type VoiceError = "denied" | "no-speech" | "failed";

/**
 * Dictation for any input. Interim words stream into `onText`; when the person stops speaking,
 * `onFinal` receives the whole phrase (e.g. to run the search straight away).
 */
export function useVoiceInput({
  locale,
  onText,
  onFinal,
}: {
  locale: Locale;
  onText: (text: string) => void;
  onFinal?: (text: string) => void;
}) {
  const supported = useSyncExternalStore(noop, () => recognitionCtor() !== null, () => false);
  const [listening, setListening] = useState(false);
  const [error, setError] = useState<VoiceError | null>(null);
  const recognition = useRef<Recognition | null>(null);
  const handlers = useRef({ onText, onFinal });
  useEffect(() => {
    handlers.current = { onText, onFinal };
  });
  useEffect(() => () => recognition.current?.abort(), []);

  const start = useCallback(() => {
    const Ctor = recognitionCtor();
    if (!Ctor) return;
    recognition.current?.abort();
    const r = new Ctor();
    r.lang = locale === "ar" ? "ar-AE" : "en-US";
    r.interimResults = true;
    r.continuous = false;
    r.maxAlternatives = 1;
    let finalText = "";
    r.onresult = (event) => {
      let text = "";
      for (let i = 0; i < event.results.length; i++) text += event.results[i][0].transcript;
      text = text.trim();
      handlers.current.onText(text);
      if (event.results[event.results.length - 1]?.isFinal) finalText = text;
    };
    r.onerror = (event) => {
      setError(event.error === "not-allowed" || event.error === "service-not-allowed" ? "denied" : event.error === "no-speech" ? "no-speech" : "failed");
    };
    r.onend = () => {
      setListening(false);
      recognition.current = null;
      if (finalText) handlers.current.onFinal?.(finalText);
    };
    recognition.current = r;
    setError(null);
    setListening(true);
    try {
      r.start();
    } catch {
      setListening(false);
      setError("failed");
    }
  }, [locale]);

  const stop = useCallback(() => recognition.current?.stop(), []);

  return { supported, listening, error, start, stop };
}
