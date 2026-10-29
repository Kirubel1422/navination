"use client";

import { Loader2, LocateFixed, MapPin, X } from "lucide-react";

import { useLocale } from "@/lib/i18n/locale";
import { useSharedLocation } from "@/lib/location";
import { cn } from "@/lib/utils";

/** "Use my location" / "Near me ✕": lets the agent look for centres near the person. */
export function LocationChip({ className }: { className?: string }) {
  const { t } = useLocale();
  const { location, status, request, clear } = useSharedLocation();
  if (location) {
    return (
      <span className={cn("inline-flex h-8 items-center gap-1 rounded-full bg-[#e5f2eb] ps-2.5 pe-1 text-xs font-medium text-[#1d5a3e]", className)}>
        <MapPin aria-hidden="true" className="size-3.5" />
        {t("locationOn")}
        <button
          type="button"
          onClick={clear}
          aria-label={t("locationClear")}
          title={t("locationClear")}
          className="grid size-6 place-items-center rounded-full hover:bg-white/70"
          data-testid="location-clear"
        >
          <X aria-hidden="true" className="size-3.5" />
        </button>
      </span>
    );
  }
  return (
    <span className={cn("inline-flex flex-col gap-1", className)}>
      <button
        type="button"
        onClick={() => void request()}
        disabled={status === "asking"}
        title={t("locationPrivacy")}
        className="inline-flex h-8 w-fit items-center gap-1.5 rounded-full border bg-card px-3 text-xs font-medium text-gulf transition-colors hover:border-gulf hover:bg-secondary disabled:opacity-60"
        data-testid="location-use"
      >
        {status === "asking" ? (
          <Loader2 aria-hidden="true" className="size-3.5 animate-spin motion-reduce:animate-none" />
        ) : (
          <LocateFixed aria-hidden="true" className="size-3.5" />
        )}
        {status === "asking" ? t("locationAsking") : t("locationUse")}
      </button>
      {(status === "denied" || status === "unavailable") && (
        <span role="alert" className="text-xs text-destructive">
          {status === "denied" ? t("locationDenied") : t("locationUnavailable")}
        </span>
      )}
    </span>
  );
}
