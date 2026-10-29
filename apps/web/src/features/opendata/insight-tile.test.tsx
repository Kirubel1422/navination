import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Insight } from "@/lib/api/types";
import { renderWithLocale } from "@/test/render";
import { InsightTile } from "./insight-tile";

const insight: Insight = {
  id: "births-all",
  headline: "1,334 births were registered in Umm Al Quwain in 2024",
  label: "births registered in Umm Al Quwain in 2024",
  detail: "+6.7% on 2023.",
  value: 1334,
  unit: "count",
  change: 6.7,
  compared_to: "2023",
  period: "2024",
  scope: "Umm Al Quwain",
  freshness: "current",
  series: [
    { label: "2022", value: 1200 },
    { label: "2023", value: 1250 },
    { label: "2024", value: 1334 },
  ],
  highlight: 2,
  source: {
    key: "mohap-live-births",
    title: "Birth 2005 - 2024",
    publisher: "Ministry of Health and Prevention",
    portal: "bayanat",
    url: "https://bayanat.ae/en/Datasets/Dataset-info?id=x",
    source_updated: "2026-03-12",
    fetched_at: "2026-10-29T05:33:43Z",
    origin: "live",
  },
};

describe("InsightTile", () => {
  it("shows the figure, what it counts, its change and a linked source", () => {
    renderWithLocale(<InsightTile insight={insight} />);
    // Once as the figure and once in the screen-reader table.
    expect(screen.getAllByText("1,334")).toHaveLength(2);
    expect(screen.getByText("births registered in Umm Al Quwain in 2024")).toBeInTheDocument();
    expect(screen.getByText("+6.7%")).toBeInTheDocument();
    expect(screen.getByText("vs 2023")).toBeInTheDocument();
    const source = screen.getByTestId("insight-source");
    expect(source).toHaveAttribute("href", insight.source.url);
    expect(source).toHaveTextContent("Ministry of Health and Prevention on Bayanat");
  });

  it("gives screen readers the series as a table and flags older data", () => {
    renderWithLocale(<InsightTile insight={{ ...insight, freshness: "older", period: "2019" }} />);
    const table = screen.getByRole("table");
    expect(within(table).getByText(insight.headline)).toBeInTheDocument();
    expect(within(table).getAllByRole("row")).toHaveLength(3);
    expect(screen.getByText("Older data (2019)")).toBeInTheDocument();
  });
});
