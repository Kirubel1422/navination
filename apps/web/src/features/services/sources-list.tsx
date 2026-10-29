"use client";

import { ExternalLink } from "lucide-react";

import type { Source } from "@/lib/api/types";
import { useLocale } from "@/lib/i18n/locale";
import { VerificationBadge } from "./badges";

export function useFormatDate() {
  const { locale } = useLocale();
  return (value: string, dateOnly = false) => {
    const date = dateOnly ? new Date(`${value}T00:00:00Z`) : new Date(value);
    return new Intl.DateTimeFormat(locale === "ar" ? "ar-AE" : "en-GB", {
      dateStyle: "medium",
      ...(dateOnly ? { timeZone: "UTC" } : { timeStyle: "short" }),
    }).format(date);
  };
}

/** Shows the source-check time separately from the page's own update date. */
export function SourcesList({ sources, highlight }: { sources: Source[]; highlight?: string[] }) {
  const { t } = useLocale();
  const format = useFormatDate();
  return (
    <ul className="divide-y rounded-2xl border bg-card" data-testid="sources-list">
      {sources.map((source) => (
        <li
          key={source.id}
          id={`source-${source.id}`}
          className={highlight?.includes(source.id) ? "bg-accent/50 p-4" : "p-4"}
        >
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{source.title}</span>
            <VerificationBadge status={source.verification_status} />
          </div>
          <p className="text-sm text-muted-foreground">{source.publisher}</p>
          <dl className="mt-1 grid gap-x-4 gap-y-0.5 text-xs text-muted-foreground sm:grid-cols-2">
            <div>
              <dt className="inline font-medium">{t("sourceChecked")}: </dt>
              <dd className="inline">{source.checked_at ? format(source.checked_at) : t("sourceNotChecked")}</dd>
            </div>
            <div>
              <dt className="inline font-medium">{t("sourceUpdated")}: </dt>
              <dd className="inline">
                {source.source_updated_at ? format(source.source_updated_at, true) : t("sourceNoDate")}
              </dd>
            </div>
          </dl>
          {source.url && (
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-flex items-center gap-1 text-sm font-medium text-gulf underline decoration-ghaf underline-offset-4 hover:decoration-gulf"
            >
              {t("sourceOpen")}: {source.title}
              <ExternalLink aria-hidden="true" className="size-3.5" />
            </a>
          )}
        </li>
      ))}
    </ul>
  );
}
