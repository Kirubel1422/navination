"use client";

import { Baby, Ban, GraduationCap, IdCard, MapPin, Pencil, Sparkles } from "lucide-react";

import { openProfileSheet } from "@/features/profile/profile-events";
import type { Journey } from "@/lib/api/types";
import { useLocale } from "@/lib/i18n/locale";
import { cn } from "@/lib/utils";
import { answerLabel, fieldLabel } from "./answer-label";

const ICONS = { emirate: MapPin, residency_status: IdCard, life_stage: Baby, degree_issued_outside_uae: GraduationCap } as const;

/**
 * How the person's answers shaped this plan: one chip per answer (hover or focus lights up the
 * stops it shaped on the map), and the services their answers rule out.
 */
export function TailoredPanel({
  journey,
  onHighlight,
  highlightField,
}: {
  journey: Journey;
  onHighlight: (field: string | null) => void;
  highlightField: string | null;
}) {
  const { t } = useLocale();
  const effects = journey.personalization;
  return (
    <section
      aria-labelledby="tailored-heading"
      className="overflow-hidden rounded-[1.5rem] bg-gradient-to-br from-[#f3effa] to-card ring-1 ring-[#6b4fa0]/15"
      data-testid="tailored-panel"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 pt-4 sm:px-6">
        <h2 id="tailored-heading" className="t-head flex items-center gap-2 text-[#3d2a66]">
          <span className="grid size-8 place-items-center rounded-full bg-dusk text-white">
            <Sparkles aria-hidden="true" className="size-4" />
          </span>
          {t("tailoredHeading")}
        </h2>
        <button
          type="button"
          onClick={openProfileSheet}
          className="inline-flex h-9 items-center gap-1.5 rounded-full border border-[#6b4fa0]/25 bg-card px-3.5 text-sm font-medium text-[#4b357c] hover:border-dusk"
        >
          <Pencil aria-hidden="true" className="size-3.5" />
          {t("tailoredEdit")}
        </button>
      </div>
      <div className="space-y-4 px-5 pt-3 pb-5 sm:px-6">
        {effects.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("tailoredNone")}</p>
        ) : (
          <ul className="flex flex-wrap gap-2" onMouseLeave={() => onHighlight(null)}>
            {effects.map((effect) => {
              const Icon = ICONS[effect.field];
              return (
                <li key={effect.field}>
                  <button
                    type="button"
                    onMouseEnter={() => onHighlight(effect.field)}
                    onFocus={() => onHighlight(effect.field)}
                    onBlur={() => onHighlight(null)}
                    aria-pressed={highlightField === effect.field}
                    className={cn(
                      "flex items-center gap-2.5 rounded-2xl border bg-card px-3 py-2 text-start transition-all",
                      highlightField === effect.field ? "border-dusk shadow-[0_0_0_3px_rgb(107_79_160/0.18)]" : "border-[#6b4fa0]/20",
                    )}
                    data-testid={`tailored-${effect.field}`}
                  >
                    <span aria-hidden="true" className="grid size-8 place-items-center rounded-full bg-[#efeaf7] text-dusk">
                      <Icon className="size-4" />
                    </span>
                    <span className="min-w-0">
                      <span className="block text-sm font-semibold">{answerLabel(t, effect.field, effect.value)}</span>
                      <span className="block text-xs text-muted-foreground">
                        <span className="sr-only">{fieldLabel(t, effect.field)}. </span>
                        {effect.step_ids.length > 0 ? t("tailoredShapes", { n: effect.step_ids.length }) : t("tailoredShapesNone")}
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
        {journey.skipped.length > 0 && (
          <div className="flex flex-wrap items-start gap-x-3 gap-y-1 text-sm">
            <span className="flex items-center gap-1.5 font-medium text-muted-foreground">
              <Ban aria-hidden="true" className="size-4" />
              {t("skippedHeading")}:
            </span>
            <ul className="flex flex-wrap gap-x-3 gap-y-1">
              {journey.skipped.map((item) => (
                <li key={item.service_id}>
                  <span className="font-medium">{item.title}</span>{" "}
                  <span className="text-muted-foreground">({answerLabel(t, item.field, String(effects.find((e) => e.field === item.field)?.value ?? ""))})</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}
