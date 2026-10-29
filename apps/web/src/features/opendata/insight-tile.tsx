"use client";

import { ExternalLink, History, TrendingDown, TrendingUp } from "lucide-react";

import type { DataSource, Insight, RelatedDataset } from "@/lib/api/types";
import { useLocale } from "@/lib/i18n/locale";
import { cn } from "@/lib/utils";
import { TrendBars, formatValue } from "./trend-bars";

export function useDataDate() {
  const { locale } = useLocale();
  return (value: string) =>
    new Intl.DateTimeFormat(locale === "ar" ? "ar-AE" : "en-GB", { dateStyle: "medium", timeZone: "UTC" }).format(
      new Date(value.length === 10 ? `${value}T00:00:00Z` : value),
    );
}

/** "Ministry of Health and Prevention on Bayanat, updated 12 Mar 2026", linked to the dataset. */
export function SourceLine({ source, className }: { source: DataSource; className?: string }) {
  const { t } = useLocale();
  const date = useDataDate();
  return (
    <p className={cn("text-xs leading-5 text-muted-foreground", className)}>
      <a
        href={source.url}
        target="_blank"
        rel="noopener noreferrer"
        className="font-medium text-foreground underline decoration-ghaf underline-offset-2 hover:decoration-gulf"
        title={source.title}
        data-testid="insight-source"
      >
        {t("insightFrom", { publisher: source.publisher, portal: t(`portal_${source.portal}`) })}
        <ExternalLink aria-hidden="true" className="ms-1 inline size-3" />
        <span className="sr-only"> {t("opensInNewTab")}</span>
      </a>
      {source.source_updated && <>, {t("insightUpdated", { date: date(source.source_updated) })}</>}
    </p>
  );
}

function Change({ insight }: { insight: Insight }) {
  const { t } = useLocale();
  if (insight.change === null || insight.change === undefined || !insight.compared_to) return null;
  const up = insight.change >= 0;
  const Icon = up ? TrendingUp : TrendingDown;
  const amount = `${up ? "+" : "−"}${Math.abs(insight.change).toFixed(Math.abs(insight.change) >= 10 ? 0 : 1)}`;
  return (
    <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-foreground">
      <Icon aria-hidden="true" className="size-3.5" />
      <span dir="ltr">{insight.unit === "percent" ? t("insightPoints", { amount }) : `${amount}%`}</span>
      <span className="text-muted-foreground">{t("insightVs", { period: insight.compared_to })}</span>
    </span>
  );
}

/** Stat tile: the figure, what it counts, its change, the trend and where it comes from. */
export function InsightTile({ insight, compact = false }: { insight: Insight; compact?: boolean }) {
  const { t } = useLocale();
  return (
    <figure
      className={cn("space-y-3", compact ? "rounded-2xl bg-salt p-3.5" : "surface p-4 sm:p-5")}
      data-testid="insight"
    >
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1.5">
        <div className="min-w-0">
          {insight.value !== null && insight.value !== undefined && (
            <p className={cn("leading-none font-semibold tracking-tight", compact ? "text-[1.6rem]" : "text-[2.1rem]")} dir="ltr">
              {formatValue(insight.value, insight.unit)}
            </p>
          )}
          <p className={cn("mt-1.5 max-w-[46ch]", compact ? "text-sm" : "text-[0.95rem]")}>{insight.label}</p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {insight.freshness === "older" && (
            <span className="inline-flex items-center gap-1 rounded-full bg-accent px-2 py-0.5 text-xs font-medium text-accent-foreground">
              <History aria-hidden="true" className="size-3.5" />
              {t("insightOlder", { period: insight.period })}
            </span>
          )}
          <Change insight={insight} />
        </div>
      </div>
      <TrendBars insight={insight} height={compact ? "h-9" : "h-14"} />
      {!compact && insight.detail && <p className="text-sm text-muted-foreground">{insight.detail}</p>}
      <figcaption>
        <SourceLine source={insight.source} />
      </figcaption>
    </figure>
  );
}

/** Other datasets on the same topic, straight from the mirrored catalogues. */
export function RelatedData({ datasets }: { datasets: RelatedDataset[] }) {
  const { t } = useLocale();
  const date = useDataDate();
  if (datasets.length === 0) return null;
  return (
    <section aria-label={t("relatedData")} className="space-y-2">
      <h3 className="t-label">{t("relatedData")}</h3>
      <ul className="divide-y rounded-2xl border bg-card">
        {datasets.map((dataset) => (
          <li key={dataset.url} className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 px-4 py-2.5" data-testid="related-dataset">
            <a
              href={dataset.url}
              target="_blank"
              rel="noopener noreferrer"
              className="min-w-0 flex-1 basis-64 text-sm font-medium underline decoration-ghaf underline-offset-2 hover:decoration-gulf"
            >
              {dataset.title}
              <span className="sr-only"> {t("opensInNewTab")}</span>
            </a>
            <span className="text-xs text-muted-foreground">
              {dataset.publisher}, {t(`portal_${dataset.portal}`)}
              {dataset.last_updated && <>, {date(dataset.last_updated)}</>}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
