"use client";

import { Check, Copy, ExternalLink, Navigation, Share2 } from "lucide-react";
import { useState, useSyncExternalStore } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import type { GeoPoint } from "@/lib/api/types";
import { useLocale } from "@/lib/i18n/locale";
import { directionsUrl, embedUrl, placeUrl, type MapTarget } from "@/lib/maps";
import { copyText } from "./contact-list";

const noop = () => () => {};

/** Live Google map with the actions people need: start a route, open in the app, copy or share. */
export function MapActions({ target, origin }: { target: MapTarget; origin?: GeoPoint }) {
  const { t } = useLocale();
  const [copied, setCopied] = useState(false);
  const canShare = useSyncExternalStore(noop, () => typeof navigator.share === "function", () => false);
  const route = directionsUrl(target, origin);
  const name = target.kind === "center" ? target.center.name : target.query;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        <a
          href={route}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex h-10 items-center gap-2 rounded-full bg-gulf px-4 text-sm font-semibold text-white hover:bg-[#0b5260]"
          data-testid="map-route"
        >
          <Navigation aria-hidden="true" className="size-4 rtl:-scale-x-100" />
          {t("mapRoute")}
          <span className="sr-only"> {t("opensInNewTab")}</span>
        </a>
        <a
          href={placeUrl(target, origin)}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex h-10 items-center gap-2 rounded-full border bg-card px-4 text-sm font-medium hover:border-gulf"
        >
          <ExternalLink aria-hidden="true" className="size-4" />
          {t("mapOpen")}
          <span className="sr-only"> {t("opensInNewTab")}</span>
        </a>
        <Button
          type="button"
          variant="outline"
          className="h-10 rounded-full bg-card px-4"
          data-testid="map-copy"
          onClick={async () => {
            if (await copyText(route)) {
              setCopied(true);
              window.setTimeout(() => setCopied(false), 2500);
            }
          }}
        >
          {copied ? <Check aria-hidden="true" className="text-mangrove" /> : <Copy aria-hidden="true" />}
          {copied ? t("copied") : t("mapCopy")}
        </Button>
        {canShare && (
          <Button
            type="button"
            variant="outline"
            className="h-10 rounded-full bg-card px-4"
            onClick={() => void navigator.share({ title: name, url: route }).catch(() => undefined)}
          >
            <Share2 aria-hidden="true" />
            {t("mapShare")}
          </Button>
        )}
      </div>
      <p aria-live="polite" className="text-xs text-muted-foreground">
        {copied ? t("mapLinkCopied") : t("nearbyMapNote")}
      </p>
    </div>
  );
}

export function MapEmbed({ target, origin, className }: { target: MapTarget; origin?: GeoPoint; className?: string }) {
  const { t, locale } = useLocale();
  const name = target.kind === "center" ? target.center.name : target.query;
  return (
    <iframe
      title={t("mapEmbedTitle", { place: name })}
      src={embedUrl(target, origin, locale)}
      loading="lazy"
      referrerPolicy="no-referrer-when-downgrade"
      className={className ?? "h-64 w-full rounded-2xl border bg-muted sm:h-72"}
      data-testid="map-embed"
    />
  );
}

/** Popup for one centre (or a search): the map plus route / open / copy / share. */
export function MapDialog({
  target,
  origin,
  open,
  onOpenChange,
}: {
  target: MapTarget | null;
  origin?: GeoPoint;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { t } = useLocale();
  if (!target) return null;
  const name = target.kind === "center" ? target.center.name : target.query;
  const address = target.kind === "center" ? target.center.address : null;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92dvh] gap-4 overflow-y-auto rounded-[1.5rem] p-5 sm:max-w-xl" data-testid="map-dialog">
        <DialogHeader>
          <DialogTitle className="t-head pe-8">{name}</DialogTitle>
          <DialogDescription>{address ?? t("mapView")}</DialogDescription>
        </DialogHeader>
        <MapEmbed target={target} origin={origin} />
        <MapActions target={target} origin={origin} />
      </DialogContent>
    </Dialog>
  );
}
