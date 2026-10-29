"use client";

import { useEffect } from "react";

import { startMockWorker } from "./browser";

export default function MockWorker({ onReady }: { onReady: () => void }) {
  useEffect(() => {
    let active = true;
    startMockWorker().then(() => {
      if (active) onReady();
    });
    return () => {
      active = false;
    };
  }, [onReady]);
  return null;
}
