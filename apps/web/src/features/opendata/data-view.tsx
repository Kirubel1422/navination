"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Database, Download, ExternalLink, History, Lightbulb, Search } from "lucide-react";
import { useDeferredValue, useState } from "react";

import { ErrorState, LoadingState } from "@/components/layout/states";
import { api } from "@/lib/api/endpoints";
import type { NavigationGaps, OpenDataSummary } from "@/lib/api/types";
import { API_BASE_URL } from "@/lib/config";
import type { MessageKey } from "@/lib/i18n/dictionaries";
import { useLocale } from "@/lib/i18n/locale";
import { cn } from "@/lib/utils";
import { RelatedData, useDataDate } from "./insight-tile";

const count = new Intl.NumberFormat("en-GB");

function Portals({ data }: { data: OpenDataSummary }) {
  const { t } = useLocale();
  return (
    <section aria-labelledby="portals" className="space-y-3">
      <h2 id="portals" className="t-head">
        {t("dataPortals")}
      </h2>
      <ul className="grid gap-3 md:grid-cols-2">
        {data.portals.map((portal) => (
          <li key={portal.portal} className="surface space-y-2 p-5" data-testid={`portal-${portal.portal}`}>
            <p className="text-[2rem] leading-none font-semibold" dir="ltr">
              {count.format(portal.datasets_indexed)}
            </p>
            <p className="text-sm text-muted-foreground">{t("dataIndexed", { n: "" }).trim()}</p>
            <a
              href={portal.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 font-medium underline decoration-ghaf underline-offset-2 hover:decoration-gulf"
            >
              {portal.name}
              <ExternalLink aria-hidden="true" className="size-3.5" />
              <span className="sr-only">{t("opensInNewTab")}</span>
            </a>
            <p className="text-xs text-muted-foreground">{portal.access}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Curated({ data }: { data: OpenDataSummary }) {
  const { t } = useLocale();
  const date = useDataDate();
  return (
    <section aria-labelledby="curated" className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="curated" className="t-head">
          {t("dataCurated")}
        </h2>
        <p className="flex items-center gap-1.5 text-sm text-muted-foreground" data-testid="sync-status">
          {data.stale ? <History aria-hidden="true" className="size-4" /> : <CheckCircle2 aria-hidden="true" className="size-4 text-mangrove" />}
          {data.last_sync?.finished_at
            ? `${t("dataSync")}: ${date(data.last_sync.finished_at)}. ${data.stale ? t("dataSyncStale") : t("dataSyncFresh")}`
            : t("dataSyncNever")}
        </p>
      </div>
      <ul className="space-y-3">
        {data.curated.map((item) => (
          <li key={item.source.key} className="surface space-y-3 p-5" data-testid="curated-dataset">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0 flex-1 basis-72">
                <a
                  href={item.source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-semibold underline decoration-ghaf underline-offset-2 hover:decoration-gulf"
                >
                  {item.source.title}
                  <span className="sr-only"> {t("opensInNewTab")}</span>
                </a>
                <p className="text-sm text-muted-foreground">
                  {t("insightFrom", { publisher: item.source.publisher, portal: t(`portal_${item.source.portal}`) })}
                  {item.source.source_updated && <>, {t("insightUpdated", { date: date(item.source.source_updated) })}</>}
                </p>
              </div>
              <div className="flex flex-wrap gap-1.5 text-xs font-medium">
                {item.data_period && (
                  <span className={cn("rounded-full px-2 py-0.5", item.freshness === "older" ? "bg-accent text-accent-foreground" : "bg-[#e5f2eb] text-[#1d5a3e]")}>
                    {item.freshness === "older" ? t("insightOlder", { period: item.data_period }) : t("dataPeriod", { period: item.data_period })}
                  </span>
                )}
                <span className="rounded-full bg-muted px-2 py-0.5">{t("dataRows", { n: count.format(item.rows) })}</span>
                <span className="rounded-full bg-muted px-2 py-0.5">{t(`dataOrigin_${item.source.origin}`)}</span>
              </div>
            </div>
            <p className="text-sm">
              <span className="text-muted-foreground">{t("dataUsedFor")}: </span>
              {item.service_titles.join(" / ")}
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function DatasetSearch() {
  const { t } = useLocale();
  const [query, setQuery] = useState("");
  const deferred = useDeferredValue(query.trim());
  const results = useQuery({
    queryKey: ["open-data-search", deferred],
    queryFn: ({ signal }) => api.searchOpenData(deferred, signal),
    enabled: deferred.length >= 2,
  });
  return (
    <section aria-labelledby="dataset-search" className="space-y-3">
      <h2 id="dataset-search" className="t-head">
        {t("dataSearchLabel")}
      </h2>
      <label className="surface flex items-center gap-2 rounded-full px-4 focus-within:border-gulf">
        <Search aria-hidden="true" className="size-4 text-muted-foreground" />
        <span className="sr-only">{t("dataSearchLabel")}</span>
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t("dataSearchPlaceholder")}
          className="h-11 min-w-0 flex-1 bg-transparent text-sm outline-none focus-visible:outline-none"
          data-testid="dataset-search"
        />
      </label>
      {results.data && results.data.length === 0 && <p className="text-sm text-muted-foreground">{t("dataSearchEmpty")}</p>}
      {results.data && <RelatedData datasets={results.data} />}
    </section>
  );
}

function topicLabel(t: (key: MessageKey) => string, topic: string): string {
  const key = `topic_${topic}` as MessageKey;
  const label = t(key);
  return label === key ? topic.replace(/[_-]+/g, " ") : label;
}

function Gaps({ gaps }: { gaps: NavigationGaps }) {
  const { t } = useLocale();
  const byTopic = new Map<string, { searches: number; no_match: number; plans: number; seconds: number[] }>();
  for (const row of gaps.rows) {
    const entry = byTopic.get(row.topic) ?? { searches: 0, no_match: 0, plans: 0, seconds: [] };
    entry.searches += row.searches;
    entry.no_match += row.no_match;
    entry.plans += row.plans;
    if (row.median_seconds_to_plan !== null) entry.seconds.push(row.median_seconds_to_plan);
    byTopic.set(row.topic, entry);
  }
  const rows = [...byTopic.entries()].sort((a, b) => b[1].searches - a[1].searches);
  const max = Math.max(1, ...rows.map(([, r]) => r.searches));
  return (
    <section aria-labelledby="gaps" className="space-y-3" data-testid="navigation-gaps">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="gaps" className="t-head">
          {t("dataGaps")}
        </h2>
        <a
          href={`${API_BASE_URL}/open-data/navigation-gaps.csv`}
          className="inline-flex h-9 items-center gap-1.5 rounded-full border bg-card px-3.5 text-sm font-medium text-gulf hover:border-gulf"
          data-testid="gaps-download"
        >
          <Download aria-hidden="true" className="size-4" />
          {t("dataGapsDownload")}
        </a>
      </div>
      <p className="max-w-[70ch] text-sm text-muted-foreground">{t("dataGapsIntro")}</p>
      {rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("dataGapsEmpty")}</p>
      ) : (
        <div className="surface overflow-x-auto">
          <table className="w-full min-w-[34rem] text-sm">
            <thead>
              <tr className="border-b text-start text-xs text-muted-foreground">
                <th scope="col" className="px-4 py-2.5 text-start font-medium">&nbsp;</th>
                <th scope="col" className="px-4 py-2.5 text-start font-medium">{t("dataSearches")}</th>
                <th scope="col" className="px-4 py-2.5 text-end font-medium">{t("dataNoMatch")}</th>
                <th scope="col" className="px-4 py-2.5 text-end font-medium">{t("dataPlans")}</th>
                <th scope="col" className="px-4 py-2.5 text-end font-medium">{t("dataMedian")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(([topic, r]) => {
                const median = r.seconds.length ? r.seconds.sort((a, b) => a - b)[Math.floor(r.seconds.length / 2)] : null;
                return (
                  <tr key={topic} className="border-b last:border-b-0">
                    <th scope="row" className="px-4 py-2.5 text-start font-medium">{topicLabel(t, topic)}</th>
                    <td className="px-4 py-2.5">
                      <span className="flex items-center gap-2">
                        <span aria-hidden="true" className="h-2 rounded-full bg-gulf" style={{ width: `${(r.searches / max) * 8}rem` }} />
                        <span className="tabular-nums">{r.searches}</span>
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-end tabular-nums">{r.no_match}</td>
                    <td className="px-4 py-2.5 text-end tabular-nums">{r.plans}</td>
                    <td className="px-4 py-2.5 text-end tabular-nums">
                      {median === null ? "—" : t("dataMinutes", { m: Math.max(1, Math.round(median / 60)) })}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function DataView() {
  const { t, locale } = useLocale();
  const summary = useQuery({ queryKey: ["open-data", locale], queryFn: ({ signal }) => api.openData(locale, signal) });
  const gaps = useQuery({ queryKey: ["navigation-gaps"], queryFn: ({ signal }) => api.navigationGaps(signal) });
  if (summary.isPending) return <LoadingState label={t("loading")} />;
  if (summary.error) return <ErrorState error={summary.error} onRetry={() => summary.refetch()} />;
  const data = summary.data;
  return (
    <div className="mx-auto max-w-4xl space-y-10" data-testid="open-data-page">
      <header className="space-y-3">
        <p className="t-label flex items-center gap-1.5">
          <Database aria-hidden="true" className="size-4" />
          {t("footerData")}
        </p>
        <h1 className="t-title max-w-[24ch]">{t("dataPageTitle")}</h1>
        <p className="max-w-[60ch] text-lg text-muted-foreground">{t("dataPageLede")}</p>
      </header>
      <Portals data={data} />
      <Curated data={data} />
      <DatasetSearch />
      {gaps.data && <Gaps gaps={gaps.data} />}
      <section aria-labelledby="findings" className="space-y-3">
        <h2 id="findings" className="t-head flex items-center gap-2">
          <Lightbulb aria-hidden="true" className="size-5 text-saffron-ink" />
          {t("dataFindings")}
        </h2>
        <ul className="space-y-2">
          {data.findings.map((finding) => (
            <li key={finding} className="flex gap-2.5 text-sm">
              <span aria-hidden="true" className="mt-2 size-1.5 shrink-0 rounded-full bg-saffron" />
              {finding}
            </li>
          ))}
        </ul>
      </section>
      <p className="border-t pt-4 text-xs text-muted-foreground">{t("dataLicence")}</p>
    </div>
  );
}
