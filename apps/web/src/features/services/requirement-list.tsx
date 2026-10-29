"use client";

import type { Requirement } from "@/lib/api/types";
import { useLocale } from "@/lib/i18n/locale";

export function RequirementList({ items, emptyLabel }: { items: Requirement[]; emptyLabel?: string }) {
  const { t } = useLocale();
  if (items.length === 0) {
    return <p className="text-sm text-muted-foreground italic">{emptyLabel ?? t("noneListed")}</p>;
  }
  return (
    <ul className="space-y-2 text-sm">
      {items.map((item) => (
        <li key={item.id} className="flex gap-2.5">
          <span aria-hidden="true" className="mt-1.5 size-2 shrink-0 rounded-full border-2 border-gulf" />
          <span>
          {item.text}{" "}
          <a href={`#source-${item.source_ids[0]}`} className="text-xs text-muted-foreground underline">
            {t("sourcesFor", { ids: item.source_ids.length })}
          </a>
          </span>
        </li>
      ))}
    </ul>
  );
}
