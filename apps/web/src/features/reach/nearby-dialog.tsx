"use client";

import { useMutation } from "@tanstack/react-query";
import { LocateFixed, MapPinned, Search } from "lucide-react";
import { useState } from "react";

import { LocationChip } from "@/components/layout/location-chip";
import { ErrorState } from "@/components/layout/states";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { api } from "@/lib/api/endpoints";
import type { Reach } from "@/lib/api/types";
import { useLocale } from "@/lib/i18n/locale";
import { useSharedLocation } from "@/lib/location";
import { useReadySession } from "@/lib/session/session-provider";
import { cn } from "@/lib/utils";
import { GuideBubble } from "./guide-bubble";
import { CentersList } from "./centers-list";
import { ContactList } from "./contact-list";
import { MapActions, MapEmbed } from "./map-dialog";

/** Map, centres and phone numbers for one result (already found, or freshly found by the agent). */
export function ReachDetails({ reach, message }: { reach: Reach; message?: string | null }) {
  const { t } = useLocale();
  const { location } = useSharedLocation();
  const origin = location ? { lat: location.lat, lng: location.lng } : undefined;
  const search = reach.map_query ? ({ kind: "search", query: reach.map_query } as const) : null;
  return (
    <div className="space-y-4">
      {message && <GuideBubble text={message} />}
      <CentersList centers={reach.centers} origin={origin} />
      {reach.centers.length === 0 && search && <p className="text-sm text-muted-foreground">{t("nearbyNone")}</p>}
      {search && (
        <div className="space-y-2">
          <MapEmbed target={search} origin={origin} />
          <MapActions target={search} origin={origin} />
        </div>
      )}
      <ContactList contacts={reach.contacts} />
    </div>
  );
}

/**
 * "Nearest centres": asks for the person's location (optional), lets them say anything specific
 * ("open on Saturday", "near Al Barsha"), and has the agent find centres and phone numbers.
 */
export function NearbyDialog({
  serviceId,
  serviceTitle,
  seed,
  className,
}: {
  serviceId: string;
  serviceTitle: string;
  seed?: Reach | null;
  className?: string;
}) {
  const { t } = useLocale();
  const { token } = useReadySession();
  const { location, status, request } = useSharedLocation();
  const [open, setOpen] = useState(false);
  const [skipLocation, setSkipLocation] = useState(false);
  const [specific, setSpecific] = useState("");
  const nearby = useMutation({
    mutationFn: () =>
      api.nearby({ token }, serviceId, {
        location: location ? { lat: location.lat, lng: location.lng } : null,
        request: specific.trim() || null,
      }),
  });
  const result = nearby.data?.reach ?? (seed && (seed.centers.length > 0 || seed.map_query) ? seed : null);
  const asking = !location && !skipLocation && !nearby.data;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button
          type="button"
          className={cn(
            "inline-flex h-9 items-center gap-1.5 rounded-full border bg-card px-3.5 text-sm font-medium text-gulf transition-colors hover:border-gulf hover:bg-secondary",
            className,
          )}
          data-testid={`nearby-open-${serviceId}`}
        >
          <MapPinned aria-hidden="true" className="size-4" />
          {t("nearbyButton")}
          <span className="sr-only">: {serviceTitle}</span>
        </button>
      </DialogTrigger>
      <DialogContent className="max-h-[92dvh] gap-5 overflow-y-auto rounded-[1.5rem] p-5 sm:max-w-2xl sm:p-6" data-testid="nearby-dialog">
        <DialogHeader>
          <DialogTitle className="t-head pe-8">{t("nearbyTitle")}</DialogTitle>
          <DialogDescription>{serviceTitle}</DialogDescription>
        </DialogHeader>

        {asking ? (
          <div className="space-y-4 rounded-2xl bg-salt p-5">
            <GuideBubble text={t("nearbyIntro")} />
            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="button"
                className="h-10 rounded-full px-4"
                disabled={status === "asking"}
                onClick={() => void request()}
                data-testid="nearby-share-location"
              >
                <LocateFixed aria-hidden="true" />
                {status === "asking" ? t("locationAsking") : t("nearbyShare")}
              </Button>
              <Button type="button" variant="ghost" className="h-10 rounded-full px-4" onClick={() => setSkipLocation(true)}>
                {t("nearbyWithout")}
              </Button>
            </div>
            {(status === "denied" || status === "unavailable") && (
              <p role="alert" className="text-sm text-destructive">
                {status === "denied" ? t("locationDenied") : t("locationUnavailable")}
              </p>
            )}
            <p className="text-xs text-muted-foreground">{t("locationPrivacy")}</p>
          </div>
        ) : (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              nearby.mutate();
            }}
            className="space-y-2"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <label htmlFor={`nearby-specific-${serviceId}`} className="t-label">
                {t("nearbySpecific")}
              </label>
              <LocationChip />
            </div>
            <div className="flex flex-wrap gap-2">
              <input
                id={`nearby-specific-${serviceId}`}
                value={specific}
                onChange={(event) => setSpecific(event.target.value)}
                maxLength={500}
                placeholder={t("nearbySpecificPlaceholder")}
                className="h-11 min-w-0 flex-1 basis-60 rounded-full border bg-card px-4 text-sm outline-none focus:border-gulf focus-visible:outline-none"
              />
              <Button type="submit" className="h-11 rounded-full px-5" disabled={nearby.isPending} data-testid="nearby-find">
                <Search aria-hidden="true" />
                {result ? t("nearbyAgain") : t("nearbyFind")}
              </Button>
            </div>
          </form>
        )}

        {nearby.isPending && (
          <div role="status" className="flex items-center gap-3 rounded-2xl bg-muted px-4 py-3 text-sm text-muted-foreground">
            <span className="typing-stops flex items-center gap-1" aria-hidden="true">
              <span />
              <span />
              <span />
            </span>
            {t("nearbySearching")}
          </div>
        )}
        {nearby.error ? <ErrorState error={nearby.error} onRetry={() => nearby.mutate()} /> : null}
        {!nearby.isPending && result && <ReachDetails reach={result} message={nearby.data?.message} />}
      </DialogContent>
    </Dialog>
  );
}
