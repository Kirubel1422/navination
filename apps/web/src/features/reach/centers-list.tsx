"use client";

import { MapPin, Navigation } from "lucide-react";
import { useState } from "react";

import type { Center, GeoPoint } from "@/lib/api/types";
import { useLocale } from "@/lib/i18n/locale";
import { distanceKm } from "@/lib/location";
import type { MapTarget } from "@/lib/maps";
import { MapDialog } from "./map-dialog";

/** Centres nearest first (distances computed in the browser; the server never sees them). */
export function CentersList({ centers, origin }: { centers: Center[]; origin?: GeoPoint }) {
  const { t } = useLocale();
  const [target, setTarget] = useState<MapTarget | null>(null);
  if (centers.length === 0) return null;
  const ranked = centers
    .map((center) => ({ center, km: origin ? distanceKm(origin, center) : null }))
    .sort((a, b) => (a.km ?? 0) - (b.km ?? 0));
  return (
    <section aria-label={t("centresHeading")} className="space-y-2">
      <h4 className="t-label flex items-center gap-1.5">
        <MapPin aria-hidden="true" className="size-3.5" />
        {t("centresHeading")}
      </h4>
      <ol className="space-y-2">
        {ranked.map(({ center, km }, index) => (
          <li key={center.id} className="flex items-start gap-3 rounded-2xl border bg-card p-3" data-testid="center">
            <span
              aria-hidden="true"
              className={`grid size-7 shrink-0 place-items-center rounded-full text-xs font-semibold ${index === 0 ? "bg-saffron text-ink" : "bg-secondary text-gulf"}`}
            >
              {index + 1}
            </span>
            <div className="min-w-0 flex-1">
              <p className="font-medium leading-snug">{center.name}</p>
              {center.address && <p className="text-xs text-muted-foreground">{center.address}</p>}
              {center.note && <p className="mt-1 text-sm">{center.note}</p>}
              {km !== null && (
                <p className="mt-1 text-xs font-semibold text-gulf">{t("kmAway", { km: km.toFixed(1) })}</p>
              )}
            </div>
            <button
              type="button"
              onClick={() => setTarget({ kind: "center", center })}
              className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-full bg-gulf px-3 text-xs font-semibold text-white hover:bg-[#0b5260]"
              data-testid="center-map"
            >
              <Navigation aria-hidden="true" className="size-3.5 rtl:-scale-x-100" />
              {t("mapRoute")}
              <span className="sr-only">: {center.name}</span>
            </button>
          </li>
        ))}
      </ol>
      <MapDialog target={target} origin={origin} open={target !== null} onOpenChange={(open) => !open && setTarget(null)} />
    </section>
  );
}
