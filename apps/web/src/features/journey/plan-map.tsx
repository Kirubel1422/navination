"use client";

import { Ban, Check, Clock3, Lock, MapPin, Sparkles, TriangleAlert } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import type { Journey, JourneyStep } from "@/lib/api/types";
import { useLocale } from "@/lib/i18n/locale";
import { cn } from "@/lib/utils";
import { answerLabel } from "./answer-label";

type StopState = "done" | "now" | "ready" | "waiting" | "check";

export function stopState(step: JourneyStep, currentId: string | null): StopState {
  if (step.progress === "completed") return "done";
  if (step.id === currentId) return "now";
  if (step.availability === "blocked") return "waiting";
  if (step.availability === "review_needed") return "check";
  return "ready";
}

const STATE_STYLE: Record<StopState, { ring: string; glyph: string }> = {
  done: { ring: "border-mangrove/60 bg-[#f3faf6]", glyph: "bg-mangrove text-white" },
  now: { ring: "border-saffron bg-card shadow-[0_0_0_5px_#fbe3b8]", glyph: "bg-saffron text-ink" },
  ready: { ring: "border-border bg-card", glyph: "bg-gulf text-white" },
  waiting: { ring: "border-dashed border-ghaf bg-card", glyph: "bg-secondary text-muted-foreground" },
  check: { ring: "border-border bg-card", glyph: "bg-accent text-saffron-ink" },
};

function Glyph({ state }: { state: StopState }) {
  const Icon = state === "done" ? Check : state === "waiting" ? Lock : state === "check" ? TriangleAlert : state === "now" ? MapPin : Clock3;
  return (
    <span aria-hidden="true" className={cn("grid size-7 shrink-0 place-items-center rounded-full", STATE_STYLE[state].glyph)}>
      <Icon className="size-3.5" strokeWidth={2.6} />
    </span>
  );
}

interface Edge {
  d: string;
  kind: "required" | "recommended";
  done: boolean;
  touches: boolean;
}

/**
 * The plan as an interactive route: stages are columns (rows on phones), stops are nodes, and
 * prerequisites are curved edges (solid = must come first, dashed = suggested order).
 */
export function PlanMap({
  journey,
  currentId,
  selectedId,
  onSelect,
  highlightField,
}: {
  journey: Journey;
  currentId: string | null;
  selectedId: string | null;
  onSelect: (stepId: string) => void;
  highlightField: string | null;
}) {
  const { t } = useLocale();
  const container = useRef<HTMLDivElement>(null);
  const nodes = useRef(new Map<string, HTMLButtonElement>());
  const [edges, setEdges] = useState<Edge[]>([]);
  const [vertical, setVertical] = useState(false);
  const [size, setSize] = useState({ w: 0, h: 0 });

  const stages = useMemo(() => {
    const groups = new Map<number, JourneyStep[]>();
    for (const step of journey.steps) groups.set(step.order_group, [...(groups.get(step.order_group) ?? []), step]);
    return [...groups.entries()].sort(([a], [b]) => a - b);
  }, [journey.steps]);
  const byId = useMemo(() => new Map(journey.steps.map((s) => [s.id, s])), [journey.steps]);

  // Edges follow the rendered stops: recomputed whenever the map is laid out or resized.
  useEffect(() => {
    const box = container.current;
    if (!box) return;
    const update = () => {
      const frame = box.getBoundingClientRect();
      setVertical(frame.width < 760);
      setSize({ w: box.scrollWidth, h: box.scrollHeight });
      const next: Edge[] = [];
      for (const dep of journey.dependencies) {
        const a = nodes.current.get(dep.from_step_id)?.getBoundingClientRect();
        const b = nodes.current.get(dep.to_step_id)?.getBoundingClientRect();
        if (!a || !b) continue;
        const ox = frame.left - box.scrollLeft;
        const oy = frame.top - box.scrollTop;
        let d: string;
        if (frame.width < 760) {
          // Stacked stops: route along the start-side gutter so lines never cross other stops.
          const rtl = getComputedStyle(box).direction === "rtl";
          const lane = 12 + (next.length % 3) * 6;
          const side = (r: DOMRect) => (rtl ? r.right - ox : r.left - ox);
          const gx = rtl ? Math.max(side(a), side(b)) + lane : Math.min(side(a), side(b)) - lane;
          const y1 = a.top + a.height * 0.65 - oy;
          const y2 = b.top + b.height * 0.35 - oy;
          const r = 10 * (rtl ? -1 : 1);
          d = `M${side(a)},${y1} H${gx + r} Q${gx},${y1} ${gx},${y1 + 10} V${y2 - 10} Q${gx},${y2} ${gx + r},${y2} H${side(b)}`;
        } else {
          const forward = a.left + a.width / 2 < b.left + b.width / 2;
          const x1 = (forward ? a.right : a.left) - ox, y1 = a.top + a.height / 2 - oy;
          const x2 = (forward ? b.left : b.right) - ox, y2 = b.top + b.height / 2 - oy;
          const dx = Math.max(28, Math.abs(x2 - x1) / 2) * (forward ? 1 : -1);
          d = `M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}`;
        }
        next.push({
          d,
          kind: dep.kind,
          done: byId.get(dep.from_step_id)?.progress === "completed",
          touches: selectedId === dep.from_step_id || selectedId === dep.to_step_id,
        });
      }
      setEdges(next);
    };
    const observer = new ResizeObserver(update);
    observer.observe(box);
    return () => observer.disconnect();
  }, [journey.dependencies, byId, selectedId, stages]);

  const skipped = journey.skipped;
  return (
    <section aria-label={t("planMapView")} className="surface overflow-hidden" data-testid="plan-map">
      <div ref={container} className="plan-map-canvas relative overflow-x-auto p-5 sm:p-7">
        <svg aria-hidden="true" className="pointer-events-none absolute inset-0" width={size.w} height={size.h}>
          <defs>
            <marker id="arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M0,0 L8,4 L0,8 z" fill="currentColor" />
            </marker>
          </defs>
          {edges.map((edge, index) => (
            <path
              key={index}
              d={edge.d}
              fill="none"
              markerEnd="url(#arrow)"
              strokeLinecap="round"
              strokeWidth={edge.touches ? 3 : 2}
              strokeDasharray={edge.kind === "required" ? undefined : "5 6"}
              className={cn(
                "transition-[stroke,stroke-width] duration-300",
                edge.done ? "text-mangrove" : edge.touches ? "text-gulf" : edge.kind === "required" ? "text-[#5f8f93]" : "text-ghaf",
              )}
              stroke="currentColor"
            />
          ))}
        </svg>

        <ol className={cn("relative flex gap-8", vertical ? "flex-col ps-9" : "min-w-max flex-row items-start gap-16")}>
          {stages.map(([group, steps], index) => {
            const done = steps.every((s) => s.progress === "completed");
            const current = steps.some((s) => s.id === currentId);
            return (
              <li key={group} className={cn("relative", vertical ? "w-full" : "w-64")} data-testid={`map-stage-${group}`}>
                <div className="mb-3 flex items-center gap-2.5">
                  <span
                    aria-hidden="true"
                    className={cn(
                      "grid size-8 shrink-0 place-items-center rounded-full text-sm font-semibold",
                      done ? "bg-mangrove text-white" : current ? "bg-saffron text-ink" : "border-2 border-ghaf bg-card text-muted-foreground",
                    )}
                  >
                    {done ? <Check className="size-4" strokeWidth={3} /> : index + 1}
                  </span>
                  <div className="min-w-0">
                    <p className="text-[0.72rem] font-medium text-muted-foreground">{t("stageHeading", { n: index + 1 })}</p>
                    <p className="truncate text-sm font-semibold">{journey.stages.find((s) => s.order_group === group)?.title}</p>
                  </div>
                </div>
                <ul className={cn("flex gap-4", vertical ? "flex-col" : "flex-col")}>
                  {steps.map((step) => {
                    const state = stopState(step, currentId);
                    const tailored = step.tailored_by.length > 0;
                    const lit = highlightField !== null && step.tailored_by.includes(highlightField as never);
                    const have = step.document_progress.filter((d) => d.status === "have").length;
                    const total = step.document_progress.length;
                    const stateLabel = t(`map${state === "now" ? "Now" : state === "done" ? "Done" : state === "waiting" ? "Waiting" : state === "check" ? "Check" : "Ready"}`);
                    return (
                      <li key={step.id} className="relative">
                        {state === "now" && (
                          <span className="map-pin absolute -top-3 start-4 z-10 inline-flex items-center gap-1 rounded-full bg-ink px-2 py-0.5 text-[0.68rem] font-semibold text-white">
                            <MapPin aria-hidden="true" className="size-3 text-saffron" />
                            {t("stageCurrent")}
                          </span>
                        )}
                        <button
                          type="button"
                          ref={(el) => {
                            if (el) nodes.current.set(step.id, el);
                            else nodes.current.delete(step.id);
                          }}
                          onClick={() => onSelect(step.id)}
                          aria-pressed={selectedId === step.id}
                          aria-label={t("mapStopLabel", { title: step.title, state: stateLabel })}
                          data-testid={`map-stop-${step.service_card.service.id}`}
                          data-state={state}
                          className={cn(
                            "group relative w-full rounded-2xl border-2 p-3 text-start transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_10px_24px_-14px_rgb(16_37_45/0.45)]",
                            STATE_STYLE[state].ring,
                            selectedId === step.id && "outline-2 outline-offset-2 outline-gulf",
                            lit && "shadow-[0_0_0_4px_rgb(107_79_160/0.28)]",
                          )}
                        >
                          <span className="flex items-start gap-2.5">
                            <Glyph state={state} />
                            <span className="min-w-0 flex-1">
                              <span className="line-clamp-2 text-sm leading-snug font-semibold">{step.title}</span>
                              <span className="mt-1 block text-[0.72rem] text-muted-foreground">{stateLabel}</span>
                            </span>
                          </span>
                          <span className="mt-2.5 flex items-center justify-between gap-2">
                            {total > 0 ? (
                              <span className="flex items-center gap-1" title={t("mapDocs", { have, total })}>
                                {step.document_progress.map((d) => (
                                  <span
                                    key={d.document_id}
                                    aria-hidden="true"
                                    className={cn("h-1.5 w-3 rounded-full", d.status === "have" ? "bg-mangrove" : d.status === "missing" ? "bg-saffron" : "bg-secondary")}
                                  />
                                ))}
                                <span className="sr-only">{t("mapDocs", { have, total })}</span>
                              </span>
                            ) : (
                              <span />
                            )}
                            {tailored && (
                              <span
                                className="inline-flex items-center gap-1 rounded-full bg-[#efeaf7] px-2 py-0.5 text-[0.68rem] font-semibold text-[#4b357c]"
                                title={t("tailoredBecause", {
                                  answers: step.tailored_by
                                    .map((f) => answerLabel(t, f, String(journey.personalization.find((p) => p.field === f)?.value ?? "")))
                                    .join(", "),
                                })}
                                data-testid="map-tailored"
                              >
                                <Sparkles aria-hidden="true" className="size-3" />
                                {t("tailoredBadge")}
                              </span>
                            )}
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </li>
            );
          })}
        </ol>
      </div>

      {skipped.length > 0 && (
        <div className="border-t border-dashed bg-salt/60 px-5 py-4 sm:px-7" data-testid="map-skipped">
          <p className="mb-2.5 flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
            <Ban aria-hidden="true" className="size-3.5" />
            {t("skippedHeading")}
          </p>
          <ul className="flex flex-wrap gap-2.5">
            {skipped.map((item) => (
              <li
                key={item.service_id}
                className={cn(
                  "max-w-xs rounded-2xl border-2 border-dashed border-ghaf/80 px-3 py-2 text-sm text-muted-foreground transition-shadow",
                  highlightField === item.field && "shadow-[0_0_0_4px_rgb(107_79_160/0.22)]",
                )}
              >
                <span className="block font-medium line-through decoration-ghaf">{item.title}</span>
                <span className="text-xs">{item.reason}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
