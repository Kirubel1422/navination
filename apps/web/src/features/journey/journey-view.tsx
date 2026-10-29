"use client";

import { AlertTriangle, Check, ListTree, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { AgentLoader } from "@/components/layout/agent-loader";
import { useAnnounce } from "@/components/layout/announcer";
import { ErrorState, LoadingState, errorMessageKey } from "@/components/layout/states";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { CoachPanel } from "@/features/coach/coach-panel";
import { ApiError } from "@/lib/api/client";
import type { DocumentStatus, JourneyStep, Progress } from "@/lib/api/types";
import { useLocale } from "@/lib/i18n/locale";
import { writeStored } from "@/lib/session/storage";
import type { HandoffState } from "./handoff-panel";
import { StepCard } from "./step-card";
import { useJourney } from "./use-journey";

type Handoffs = Record<string, { official?: HandoffState; support?: HandoffState }>;

export function JourneyView() {
  const params = useParams<{ journeyId: string }>();
  const journeyId = decodeURIComponent(params.journeyId);
  const { t } = useLocale();
  const announce = useAnnounce();
  const { journey, updateStep, replan, handoff } = useJourney(journeyId);
  const [coachStepId, setCoachStepId] = useState<string | null>(null);
  const [focusedStep, setFocusedStep] = useState<string | null>(null);
  const [stepErrors, setStepErrors] = useState<Record<string, string>>({});
  const [handoffs, setHandoffs] = useState<Handoffs>({});
  const [rediscover, setRediscover] = useState(false);

  useEffect(() => {
    if (journey.data) writeStored("activeJourney", journey.data.id);
  }, [journey.data]);

  const stages = useMemo(() => {
    const groups = new Map<number, JourneyStep[]>();
    for (const step of journey.data?.steps ?? []) {
      groups.set(step.order_group, [...(groups.get(step.order_group) ?? []), step]);
    }
    return [...groups.entries()].sort(([a], [b]) => a - b);
  }, [journey.data]);

  if (journey.isPending) return <LoadingState label={t("journeyLoading")} />;
  if (journey.error) {
    if (journey.error instanceof ApiError && journey.error.status === 404) {
      return (
        <div className="space-y-3">
          <p role="alert">{t("journeyNotFound")}</p>
          <Button asChild>
            <Link href="/">{t("home")}</Link>
          </Button>
        </div>
      );
    }
    return <ErrorState error={journey.error} onRetry={() => journey.refetch()} />;
  }

  const data = journey.data;
  const defaultStep = data.steps.find((s) => s.progress !== "completed")?.id ?? null;
  const completed = data.steps.filter((s) => s.progress === "completed").length;
  const activeCoachStep = coachStepId && data.steps.some((s) => s.id === coachStepId) ? coachStepId : defaultStep;

  const viewStep = (stepId: string) => {
    setFocusedStep(stepId);
    const element = document.getElementById(`step-${stepId}`);
    element?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    element?.focus({ preventScroll: true });
  };

  const mutateStep = (stepId: string, body: { progress?: Progress; document_progress?: { document_id: string; status: DocumentStatus }[] }) => {
    setStepErrors((current) => Object.fromEntries(Object.entries(current).filter(([id]) => id !== stepId)));
    updateStep.mutate(
      { stepId, body },
      {
        onSuccess: () => announce(t("saved")),
        onError: (error) => {
          const message =
            error instanceof ApiError && error.code === "PREREQUISITES_INCOMPLETE"
              ? t("prerequisitesIncomplete")
              : t(errorMessageKey(error));
          setStepErrors((current) => ({ ...current, [stepId]: message }));
          announce(message);
          if (error instanceof ApiError && error.code === "CONTEXT_STALE") void journey.refetch();
        },
      },
    );
  };

  const requestHandoff = (stepId: string, kind: "official" | "support") => {
    setHandoffs((current) => ({ ...current, [stepId]: { ...current[stepId], [kind]: { status: "pending" } } }));
    handoff.mutate(
      { step_id: stepId, kind },
      {
        onSuccess: (result) =>
          setHandoffs((current) => ({ ...current, [stepId]: { ...current[stepId], [kind]: { status: "ready", handoff: result } } })),
        onError: (error) => {
          setHandoffs((current) => ({ ...current, [stepId]: { ...current[stepId], [kind]: { status: "error", error } } }));
          if (error instanceof ApiError && error.code === "CONTEXT_STALE") void journey.refetch();
        },
      },
    );
    viewStep(stepId);
  };

  const doReplan = () =>
    replan.mutate(undefined, {
      onSuccess: () => {
        setHandoffs({});
        setStepErrors({});
        announce(t("saved"));
      },
      onError: (error) => {
        if (error instanceof ApiError && error.code === "CONTEXT_STALE") setRediscover(true);
      },
    });

  const stageState = (steps: JourneyStep[], index: number): "done" | "current" | "upcoming" => {
    if (steps.every((st) => st.progress === "completed")) return "done";
    const firstOpen = stages.findIndex(([, st]) => st.some((x) => x.progress !== "completed"));
    return index === firstOpen ? "current" : "upcoming";
  };

  return (
    <div className="space-y-8">
      <header className="grid grid-cols-1 items-end gap-x-10 gap-y-5 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-2">
          <p className="t-label">{t("yourRoute")}</p>
          <h1 className="t-title max-w-[24ch]" data-testid="journey-title">
            {data.title}
          </h1>
        </div>
        <div className="space-y-2.5">
          <div className="flex items-baseline justify-between gap-3">
            <p className="text-sm font-semibold">{t("journeyProgress", { done: completed, total: data.steps.length })}</p>
            {defaultStep && (
              <Button variant="link" size="sm" className="h-auto px-0 text-gulf" onClick={() => viewStep(defaultStep)}>
                {t("nextStep")}
              </Button>
            )}
          </div>
          <progress aria-label={t("progressUserReported")} value={completed} max={data.steps.length || 1} className="sr-only" />
          <div className="progress-tiles" aria-hidden="true">
            {data.steps.map((step) => (
              <span key={step.id} data-state={step.progress === "completed" ? "done" : step.id === defaultStep ? "current" : "todo"} />
            ))}
          </div>
          <p className="text-xs text-muted-foreground">{t("progressNote")}</p>
        </div>
      </header>

      {data.is_stale && (
        <Alert variant="destructive" data-testid="stale-banner" className="rounded-2xl">
          <AlertTriangle aria-hidden="true" />
          <AlertTitle>{rediscover ? t("rediscoverTitle") : t("staleTitle")}</AlertTitle>
          <AlertDescription className="space-y-2">
            <p>{rediscover ? t("rediscoverBody") : t("staleBody")}</p>
            {replan.error && !rediscover ? <ErrorState error={replan.error} /> : null}
            {rediscover ? (
              <Button asChild size="sm" variant="outline" className="rounded-full">
                <Link href="/">{t("rediscoverAction")}</Link>
              </Button>
            ) : (
              <Button size="sm" className="h-9 rounded-full px-4" onClick={doReplan} disabled={replan.isPending} data-testid="replan">
                <RefreshCw aria-hidden="true" className={replan.isPending ? "animate-spin motion-reduce:animate-none" : ""} />
                {replan.isPending ? t("replanning") : t("replan")}
              </Button>
            )}
          </AlertDescription>
        </Alert>
      )}

      {data.notices.length > 0 && (
        <section aria-labelledby="notices-heading" className="flex gap-3 rounded-2xl bg-accent/60 px-4 py-3">
          <ListTree aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-saffron-ink" />
          <div>
            <h2 id="notices-heading" className="sr-only">
              {t("noticesHeading")}
            </h2>
            <ul className="space-y-1 text-sm" data-testid="journey-notices">
              {data.notices.map((notice) => (
                <li key={notice}>{notice}</li>
              ))}
            </ul>
          </div>
        </section>
      )}

      <div className="grid grid-cols-1 items-start gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <ol className="stage-line min-w-0" aria-label={data.title}>
          {stages.map(([group, steps], index) => {
            const stage = data.stages.find((s) => s.order_group === group);
            const state = stageState(steps, index);
            return (
              <li key={group} aria-labelledby={`stage-${data.id}-${group}`} data-state={state} data-testid={`stage-${group}`}>
                <span className="stage-marker" aria-hidden="true">
                  {state === "done" ? <Check className="size-4" strokeWidth={3} /> : group + 1}
                </span>
                <div className="stage-body min-w-0 space-y-4">
                  <div className="space-y-1 pt-1">
                    <p className="flex flex-wrap items-center gap-2 text-[0.8rem] font-medium text-muted-foreground">
                      {t("stageHeading", { n: group + 1 })}
                      {state === "current" && (
                        <span className="rounded-full bg-saffron px-2 py-0.5 text-[0.72rem] font-semibold text-ink">{t("stageCurrent")}</span>
                      )}
                      {state === "done" && (
                        <span className="rounded-full bg-[#e5f2eb] px-2 py-0.5 text-[0.72rem] font-semibold text-[#1d5a3e]">{t("stageDone")}</span>
                      )}
                      {state === "upcoming" && <span className="sr-only">{t("stageUpcoming")}</span>}
                    </p>
                    <h2 id={`stage-${data.id}-${group}`} className="t-head">
                      {stage?.title ?? t("stageFallback", { n: group + 1 })}
                    </h2>
                    {stage?.description && <p className="max-w-[65ch] text-sm text-muted-foreground">{stage.description}</p>}
                    <p className="text-xs text-muted-foreground">{steps.length > 1 ? t("stageParallel") : t("stageSingle")}</p>
                  </div>
                  <ul className="space-y-4">
                    {steps.map((step) => (
                      <li key={step.id}>
                        <StepCard
                          journey={data}
                          step={step}
                          locked={data.is_stale}
                          pending={updateStep.isPending && updateStep.variables?.stepId === step.id}
                          error={stepErrors[step.id] ?? null}
                          focused={focusedStep === step.id}
                          handoffs={handoffs[step.id] ?? {}}
                          onProgress={(progress) => mutateStep(step.id, { progress })}
                          onDocument={(documentId, status) =>
                            mutateStep(step.id, { document_progress: [{ document_id: documentId, status }] })
                          }
                          onAskCoach={() => {
                            setCoachStepId(step.id);
                            document.getElementById(`coach-input-${data.id}`)?.focus();
                          }}
                          onHandoff={(kind) => requestHandoff(step.id, kind)}
                        />
                      </li>
                    ))}
                  </ul>
                </div>
              </li>
            );
          })}
        </ol>
        <aside aria-label={t("coachHeading")} className="lg:sticky lg:top-28">
          <CoachPanel journey={data} stepId={activeCoachStep} onViewStep={viewStep} onHandoff={requestHandoff} />
        </aside>
      </div>

      <AgentLoader open={replan.isPending} runId={replan.submittedAt} task="replan" />
    </div>
  );
}
