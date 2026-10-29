"use client";

import { useState } from "react";

import type { Insight } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const numbers = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 1 });

export function formatValue(value: number, unit: Insight["unit"]): string {
  return unit === "percent" ? `${Math.round(value)}%` : numbers.format(Math.round(value));
}

/**
 * A single-series trend: muted bars with the key period in the accent (stat-tile sparkline).
 * Hover or focus shows the value; screen readers get the same numbers as a table.
 */
export function TrendBars({
  insight,
  className,
  height = "h-12",
}: {
  insight: Insight;
  className?: string;
  height?: string;
}) {
  const [active, setActive] = useState<number | null>(null);
  const points = insight.series;
  if (points.length < 2) return null;
  const max = Math.max(...points.map((p) => p.value), 1);
  const accent = insight.highlight ?? points.length - 1;
  const shown = active ?? accent;
  return (
    <div className={cn("relative", className)}>
      <div
        className={cn("flex items-end gap-[2px]", height)}
        aria-hidden="true"
        onMouseLeave={() => setActive(null)}
      >
        {points.map((point, index) => (
          <span
            key={`${point.label}-${index}`}
            onMouseEnter={() => setActive(index)}
            className={cn(
              "min-h-[2px] flex-1 rounded-t-[4px] transition-colors",
              index === accent ? "bg-gulf" : "bg-ghaf/70",
              active === index && index !== accent && "bg-ghaf",
            )}
            style={{ height: `${Math.max(4, (point.value / max) * 100)}%` }}
          />
        ))}
      </div>
      <div className="mt-1 flex items-center justify-between text-[0.7rem] text-muted-foreground" aria-hidden="true">
        <span>{points[0].label}</span>
        <span className="font-medium text-foreground">
          {points[shown].label}: {formatValue(points[shown].value, insight.unit)}
        </span>
        <span>{points[points.length - 1].label}</span>
      </div>
      <table className="sr-only">
        <caption>{insight.headline}</caption>
        <tbody>
          {points.map((point, index) => (
            <tr key={`${point.label}-${index}`}>
              <th scope="row">{point.label}</th>
              <td>{formatValue(point.value, insight.unit)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
