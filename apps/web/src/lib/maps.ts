/**
 * Google Maps links that need no API key. On a phone, maps.google.com links open the Google Maps
 * app; on a computer they open in the browser.
 */
import type { Center, GeoPoint } from "@/lib/api/types";

const pt = (p: GeoPoint) => `${p.lat},${p.lng}`;

export type MapTarget = { kind: "center"; center: Center } | { kind: "search"; query: string };

/** Turn-by-turn directions to a centre (from the person's location when shared). */
export function directionsUrl(target: MapTarget, origin?: GeoPoint): string {
  const params = new URLSearchParams({ api: "1", travelmode: "driving" });
  params.set("destination", target.kind === "center" ? pt(target.center) : target.query);
  if (origin) params.set("origin", pt(origin));
  return `https://www.google.com/maps/dir/?${params}`;
}

/** The place itself (or a search near the person), to open or share. */
export function placeUrl(target: MapTarget, near?: GeoPoint): string {
  if (target.kind === "center") {
    const params = new URLSearchParams({ api: "1", query: `${target.center.name} ${pt(target.center)}` });
    return `https://www.google.com/maps/search/?${params}`;
  }
  const query = encodeURIComponent(target.query);
  return near
    ? `https://www.google.com/maps/search/${query}/@${pt(near)},13z`
    : `https://www.google.com/maps/search/?api=1&query=${query}`;
}

/** An embeddable map (no key needed): a pin on the centre, or live search results near the person. */
export function embedUrl(target: MapTarget, near?: GeoPoint, locale = "en"): string {
  const params = new URLSearchParams({ output: "embed", hl: locale });
  if (target.kind === "center") {
    params.set("q", pt(target.center));
    params.set("z", "16");
  } else if (near) {
    // `ll` centres the live search on the person, so the pins are the centres around them.
    params.set("q", target.query);
    params.set("ll", pt(near));
    params.set("z", "13");
  } else {
    params.set("q", `${target.query}, UAE`);
    params.set("z", "10");
  }
  return `https://maps.google.com/maps?${params}`;
}
