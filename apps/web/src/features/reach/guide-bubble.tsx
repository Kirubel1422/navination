"use client";

import { ExternalLink } from "lucide-react";

import { Mark } from "@/components/layout/mark";
import type { Source } from "@/lib/api/types";
import { useLocale } from "@/lib/i18n/locale";
import { cn } from "@/lib/utils";

/** Navi speaking: a direct answer, with the references it rests on. */
export function GuideBubble({
  text,
  sources = [],
  size = "md",
  testId,
}: {
  text: string;
  sources?: Source[];
  size?: "md" | "lg";
  testId?: string;
}) {
  const { t } = useLocale();
  return (
    <div className="flex items-start gap-3" data-testid={testId}>
      <Mark className={size === "lg" ? "size-10" : "size-8"} />
      <div className="min-w-0 flex-1">
        <p className="sr-only">{t("guideName")}:</p>
        <div
          className={cn(
            "rounded-2xl rounded-ss-sm bg-card ring-1 ring-border",
            size === "lg" ? "px-5 py-4 text-[1.05rem] leading-7" : "px-4 py-3 text-[0.95rem]",
          )}
        >
          <p className="whitespace-pre-line">{text}</p>
          {sources.length > 0 && (
            <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t pt-3">
              <span className="text-xs font-medium text-muted-foreground">{t("guideSources")}:</span>
              {sources.map((source) =>
                source.url ? (
                  <a
                    key={source.id}
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex max-w-full items-center gap-1 rounded-full bg-secondary px-2.5 py-1 text-xs font-medium text-gulf hover:bg-[#d5e5e1]"
                  >
                    <span className="truncate">{source.title}</span>
                    <ExternalLink aria-hidden="true" className="size-3 shrink-0" />
                    <span className="sr-only">{t("opensInNewTab")}</span>
                  </a>
                ) : (
                  <span key={source.id} className="rounded-full bg-secondary px-2.5 py-1 text-xs">
                    {source.title}
                  </span>
                ),
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
