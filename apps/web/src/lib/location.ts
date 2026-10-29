"use client";

import { useCallback, useState } from "react";

import type { GeoPoint } from "@/lib/api/types";
import { readStored, removeStored, useStored, writeStored } from "@/lib/session/storage";

/**
 * The person's location, only when they choose to share it. It is rounded to about 100 m, kept in
 * this tab's sessionStorage, and sent with a request only to find nearby centres (the API never
 * stores it).
 */
export interface SharedLocation extends GeoPoint {
  at: number;
}

export type LocationStatus = "idle" | "asking" | "denied" | "unavailable";

const round = (value: number) => Math.round(value * 1000) / 1000;

/** The shared location for a request body, or undefined (the field is then omitted). */
export function sharedPoint(): GeoPoint | undefined {
  const stored = readStored<SharedLocation>("location");
  return stored ? { lat: stored.lat, lng: stored.lng } : undefined;
}

export function useSharedLocation() {
  const location = useStored<SharedLocation>("location");
  const [status, setStatus] = useState<LocationStatus>("idle");

  const request = useCallback(
    () =>
      new Promise<SharedLocation | null>((resolve) => {
        if (typeof navigator === "undefined" || !("geolocation" in navigator)) {
          setStatus("unavailable");
          resolve(null);
          return;
        }
        setStatus("asking");
        navigator.geolocation.getCurrentPosition(
          (position) => {
            const value: SharedLocation = {
              lat: round(position.coords.latitude),
              lng: round(position.coords.longitude),
              at: Date.now(),
            };
            writeStored("location", value);
            setStatus("idle");
            resolve(value);
          },
          (error) => {
            setStatus(error.code === error.PERMISSION_DENIED ? "denied" : "unavailable");
            resolve(null);
          },
          { enableHighAccuracy: false, timeout: 15_000, maximumAge: 10 * 60_000 },
        );
      }),
    [],
  );

  const clear = useCallback(() => {
    removeStored("location");
    setStatus("idle");
  }, []);

  return { location, status, request, clear };
}

/** Straight-line distance in km, for ordering centres in the browser. */
export function distanceKm(a: GeoPoint, b: GeoPoint): number {
  const rad = (d: number) => (d * Math.PI) / 180;
  const h =
    Math.sin(rad(b.lat - a.lat) / 2) ** 2 +
    Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(rad(b.lng - a.lng) / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.sqrt(h));
}
