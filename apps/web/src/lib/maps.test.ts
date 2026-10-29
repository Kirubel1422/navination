import { describe, expect, it } from "vitest";

import { distanceKm } from "./location";
import { directionsUrl, embedUrl, placeUrl } from "./maps";

const center = { id: "c1", name: "Tasheel Al Muraqqabat", address: null, lat: 25.2653, lng: 55.3259, note: null, source: "openstreetmap" as const };

describe("Google Maps links", () => {
  it("routes from the person to the centre", () => {
    const url = new URL(directionsUrl({ kind: "center", center }, { lat: 25.11, lng: 55.2 }));
    expect(url.origin + url.pathname).toBe("https://www.google.com/maps/dir/");
    expect(url.searchParams.get("destination")).toBe("25.2653,55.3259");
    expect(url.searchParams.get("origin")).toBe("25.11,55.2");
  });

  it("searches near the person when no centre is known, and embeds without a key", () => {
    expect(placeUrl({ kind: "search", query: "Tasheel centre" }, { lat: 25.1, lng: 55.2 })).toBe(
      "https://www.google.com/maps/search/Tasheel%20centre/@25.1,55.2,13z",
    );
    const embed = new URL(embedUrl({ kind: "search", query: "Tasheel centre" }, { lat: 25.1, lng: 55.2 }, "ar"));
    expect(embed.searchParams.get("output")).toBe("embed");
    expect(embed.searchParams.get("q")).toBe("Tasheel centre");
    expect(embed.searchParams.get("ll")).toBe("25.1,55.2");
    expect(embed.searchParams.get("hl")).toBe("ar");
  });

  it("measures distance in km", () => {
    expect(distanceKm({ lat: 25.2048, lng: 55.2708 }, { lat: 24.4539, lng: 54.3773 })).toBeCloseTo(124, -1);
  });
});
