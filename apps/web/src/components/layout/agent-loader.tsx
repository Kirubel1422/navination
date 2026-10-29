"use client";

import { Dialog as DialogPrimitive } from "radix-ui";
import { useEffect, useState, useSyncExternalStore } from "react";

import { Button } from "@/components/ui/button";
import type { MessageKey } from "@/lib/i18n/dictionaries";
import { useLocale } from "@/lib/i18n/locale";

export type AgentTask = "search" | "plan" | "replan";

const TITLES: Record<AgentTask, MessageKey> = {
  search: "loaderSearchTitle",
  plan: "loaderPlanTitle",
  replan: "loaderReplanTitle",
};

const PHASES: Record<AgentTask, MessageKey[]> = {
  search: ["loaderSearch1", "loaderSearch2", "loaderSearch3", "loaderSearch4"],
  plan: ["loaderPlan1", "loaderPlan2", "loaderPlan3", "loaderPlan4"],
  replan: ["loaderPlan1", "loaderPlan2", "loaderPlan3", "loaderPlan4"],
};

/** Seconds spent in each phase before the route moves on; the last phase holds until done. */
const PHASE_SECONDS = 5;
/** How much of the route is drawn while each phase runs (it never completes before the answer). */
const DRAWN = [10, 38, 68, 90];
const STATIONS = [
  { x: 30, y: 74 },
  { x: 114, y: 44 },
  { x: 198, y: 62 },
];
const ROUTE = "M30 74 C64 74 80 44 114 44 C148 44 164 62 198 62 C232 62 250 30 282 30";

function subscribeReducedMotion(callback: () => void) {
  const query = window.matchMedia("(prefers-reduced-motion: reduce)");
  query.addEventListener("change", callback);
  return () => query.removeEventListener("change", callback);
}

function useReducedMotion() {
  return useSyncExternalStore(
    subscribeReducedMotion,
    () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    () => true,
  );
}

function formatElapsed(seconds: number) {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

function LoaderBody({ task, onHide }: { task: AgentTask; onHide: () => void }) {
  const { t } = useLocale();
  const reduced = useReducedMotion();
  const [startedAt] = useState(() => Date.now());
  const [now, setNow] = useState(startedAt);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const elapsed = Math.max(0, Math.floor((now - startedAt) / 1000));
  const phases = PHASES[task];
  const phase = Math.min(Math.floor(elapsed / PHASE_SECONDS), phases.length - 1);
  const drawn = DRAWN[phase];

  return (
    <>
      <div className="relative h-44 overflow-hidden bg-gradient-to-b from-white to-salt" aria-hidden="true">
        {/* eslint-disable-next-line @next/next/no-img-element -- tiny pixel-art asset, scaled with nearest-neighbour */}
        <img src="/art/dunes.png" alt="" className="pixel art-flip absolute inset-x-0 bottom-0 h-16 w-full object-cover object-[30%_bottom]" />
        <svg viewBox="0 0 320 132" preserveAspectRatio="xMidYMin meet" className="art-flip absolute inset-x-0 top-2 h-full w-full">
          <path d={ROUTE} fill="none" stroke="#9db8b4" strokeWidth="2.5" strokeDasharray="1 6" strokeLinecap="round" />
          <path
            d={ROUTE}
            pathLength={100}
            fill="none"
            stroke="#0e6170"
            strokeWidth="4"
            strokeLinecap="round"
            strokeDasharray="100"
            strokeDashoffset={100 - drawn}
            className="loader-route"
          />
          {!reduced && (
            <circle r="5" fill="#e9a23b" stroke="#fff" strokeWidth="2">
              <animateMotion
                dur="2.4s"
                repeatCount="indefinite"
                path={ROUTE}
                keyPoints={`0;${drawn / 100}`}
                keyTimes="0;1"
                calcMode="linear"
              />
            </circle>
          )}
          {STATIONS.map((station, index) => {
            const reached = phase > index;
            const current = phase === index;
            return (
              <g key={index}>
                {current && <circle cx={station.x} cy={station.y} r="7" fill="#e9a23b" className="loader-pulse" />}
                <circle
                  cx={station.x}
                  cy={station.y}
                  r="7"
                  fill={reached ? "#0e6170" : current ? "#e9a23b" : "#fff"}
                  stroke={reached ? "#0e6170" : current ? "#e9a23b" : "#9db8b4"}
                  strokeWidth="2.5"
                />
                {reached && <path d={`M${station.x - 3} ${station.y} l2 2.4 l4 -4.6`} stroke="#fff" strokeWidth="1.8" fill="none" strokeLinecap="round" />}
              </g>
            );
          })}
          <image href="/art/sun.png" x="258" y="6" width="48" height="48" className="pixel loader-sun" />
        </svg>
      </div>
      <div className="sadu-band loader-weave" aria-hidden="true" />
      <div className="space-y-4 p-6 pt-5">
        <div>
          <DialogPrimitive.Title className="t-head">{t(TITLES[task])}</DialogPrimitive.Title>
          <DialogPrimitive.Description asChild>
            <p key={phase} aria-live="polite" className="loader-phase mt-1 text-[0.95rem] text-muted-foreground" data-testid="agent-loader-phase">
              {t(phases[phase])}
            </p>
          </DialogPrimitive.Description>
        </div>
        <ol className="flex gap-1.5" aria-hidden="true">
          {phases.map((key, index) => (
            <li
              key={key}
              className={`h-1.5 flex-1 rounded-full transition-colors duration-500 ${index < phase ? "bg-gulf" : index === phase ? "bg-saffron" : "bg-secondary"}`}
            />
          ))}
        </ol>
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm text-muted-foreground">
            <span className="tabular-nums">{t("loaderElapsed", { time: formatElapsed(elapsed) })}</span>
            <span className="hidden sm:inline">. {t("loaderNote")}</span>
          </p>
          <Button variant="ghost" size="sm" onClick={onHide}>
            {t("loaderHide")}
          </Button>
        </div>
      </div>
    </>
  );
}

/**
 * A modal shown while an AI agent run is in flight. The request keeps running if the person hides
 * it; the page's inline status stays visible. `runId` (the mutation's submittedAt) makes "hide"
 * apply to one run only.
 */
export function AgentLoader({ open, runId, task }: { open: boolean; runId: number; task: AgentTask }) {
  const [hiddenRun, setHiddenRun] = useState<number | null>(null);
  const visible = open && hiddenRun !== runId;
  return (
    <DialogPrimitive.Root open={visible} onOpenChange={(next) => !next && setHiddenRun(runId)}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-ink/40 backdrop-blur-[3px] data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0" />
        <DialogPrimitive.Content
          data-testid="agent-loader"
          onPointerDownOutside={(event) => event.preventDefault()}
          className="fixed top-1/2 start-1/2 z-50 w-[min(26rem,calc(100%-2rem))] -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-[1.75rem] bg-card shadow-[0_30px_80px_-20px_rgb(16_37_45/0.45)] outline-none rtl:translate-x-1/2 data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95 data-closed:animate-out data-closed:fade-out-0"
        >
          {visible && <LoaderBody key={runId} task={task} onHide={() => setHiddenRun(runId)} />}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
