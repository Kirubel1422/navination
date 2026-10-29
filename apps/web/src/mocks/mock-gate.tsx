"use client";

import dynamic from "next/dynamic";
import { useState } from "react";

import { API_MODE } from "@/lib/config";

// Loaded only in the browser: msw/browser has no server build.
const MockWorker = dynamic(() => import("./mock-worker"), { ssr: false });

/**
 * In mock mode, start the MSW service worker before any request is made. In live mode this is a
 * pass-through: there is never an automatic fallback from live to mock data.
 */
export function MockGate({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  if (API_MODE === "live") return <>{children}</>;
  return ready ? <>{children}</> : <MockWorker onReady={() => setReady(true)} />;
}
