"use client";

import { Building2, Check, CircleDashed, ClipboardCheck, MessageCircleQuestion } from "lucide-react";
import Link from "next/link";
import { useId } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { AvailabilityBadge, OriginBadge, VerificationBadge } from "@/features/services/badges";
import { AuthorityNote } from "@/features/services/service-card";
import type { Dependency, DocumentStatus, Journey, JourneyStep, Progress } from "@/lib/api/types";
import { useLocale } from "@/lib/i18n/locale";
import { cn } from "@/lib/utils";
import { DocumentChecklist } from "./document-checklist";
import { HandoffPanel, type HandoffState } from "./handoff-panel";

const PROGRESS: Progress[] = ["not_started", "in_progress", "completed"];

/** Small station glyph for a step's self-reported progress. */
function ProgressGlyph({ progress }: { progress: Progress }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "mt-1 grid size-6 shrink-0 place-items-center rounded-full border-2",
        progress === "completed" && "border-mangrove bg-mangrove text-white",
        progress === "in_progress" && "border-saffron bg-[conic-gradient(var(--saffron)_50%,transparent_0)]",
        progress === "not_started" && "border-ghaf",
      )}
    >
      {progress === "completed" && <Check className="size-3.5" strokeWidth={3} />}
    </span>
  );
}

export function StepCard({
  journey,
  step,
  locked,
  pending,
  error,
  focused,
  handoffs,
  onProgress,
  onDocument,
  onAskCoach,
  onHandoff,
}: {
  journey: Journey;
  step: JourneyStep;
  locked: boolean;
  pending: boolean;
  error: string | null;
  focused: boolean;
  handoffs: { official?: HandoffState; support?: HandoffState };
  onProgress: (progress: Progress) => void;
  onDocument: (documentId: string, status: DocumentStatus) => void;
  onAskCoach: () => void;
  onHandoff: (kind: "official" | "support") => void;
}) {
  const { t, dir } = useLocale();
  const progressId = useId();
  const { service } = step.service_card;
  const titleOf = (stepId: string) => journey.steps.find((s) => s.id === stepId)?.title ?? stepId;
  const incoming: Dependency[] = journey.dependencies.filter((d) => d.to_step_id === step.id);

  return (
    <article
      id={`step-${step.id}`}
      tabIndex={-1}
      aria-labelledby={`step-title-${step.id}`}
      data-progress={step.progress}
      className={cn(
        "surface scroll-mt-32 space-y-5 p-5 outline-none sm:p-6",
        step.progress === "completed" && "bg-[#fbfdfc]",
        focused && "border-gulf shadow-[0_0_0_3px_rgb(14_97_112/0.18)]",
      )}
      data-testid={`step-${service.id}`}
    >
      <header className="space-y-2">
        <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
          <div className="flex min-w-0 flex-1 basis-64 items-start gap-3">
            <ProgressGlyph progress={step.progress} />
            <div className="min-w-0">
              <h3 id={`step-title-${step.id}`} className="text-[1.1rem] leading-snug font-semibold">
                {step.title}
              </h3>
              <p className="mt-0.5 flex items-center gap-1.5 text-sm text-muted-foreground">
                <Building2 aria-hidden="true" className="size-3.5 shrink-0" />
                {service.entity}
              </p>
            </div>
          </div>
          <AvailabilityBadge availability={step.availability} />
        </div>
        <div className="flex flex-wrap gap-2 sm:ps-9">
          <VerificationBadge status={service.verification_status} />
          <OriginBadge origin={service.origin} />
        </div>
      </header>

      <div className="space-y-1 sm:ps-9">
        <p className="max-w-[68ch]" data-testid="step-instructions">
          {step.instructions}
        </p>
        {step.title !== service.title && <p className="text-xs text-muted-foreground">{service.title}</p>}
      </div>

      {incoming.length > 0 && (
        <section aria-label={t("prerequisites")} className="sm:ms-9 space-y-2 rounded-2xl bg-muted/70 p-3">
          <h4 className="t-label">{t("prerequisites")}</h4>
          <ul className="space-y-2 text-sm">
            {incoming.map((dep) => (
              <li key={`${dep.from_step_id}-${dep.to_step_id}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={cn(
                      "rounded-full px-2 py-0.5 text-[0.72rem] font-semibold",
                      dep.kind === "required" ? "bg-ink text-white" : "bg-card text-muted-foreground ring-1 ring-border",
                    )}
                  >
                    {dep.kind === "required" ? t("requiredBadge") : t("recommendedBadge")}
                  </span>
                  <a href={`#step-${dep.from_step_id}`} className="font-medium underline decoration-ghaf underline-offset-4 hover:decoration-gulf">
                    {titleOf(dep.from_step_id)}
                  </a>
                  {step.blocker_step_ids.includes(dep.from_step_id) && (
                    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                      <CircleDashed aria-hidden="true" className="size-3" />
                      {t("blockedBy")}
                    </span>
                  )}
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{dep.explanation}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-label={t("documentsChecklist")} className="space-y-2 sm:ps-9">
        <h4 className="flex items-center gap-1.5 t-label">
          <ClipboardCheck aria-hidden="true" className="size-4" />
          {t("documentsChecklist")}
        </h4>
        <DocumentChecklist step={step} disabled={locked || pending} onChange={onDocument} />
      </section>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 sm:ps-9">
        <Label htmlFor={progressId} className="t-label">
          {t("progressUserReported")}
        </Label>
        <Select value={step.progress} onValueChange={(value) => onProgress(value as Progress)} disabled={locked || pending} dir={dir}>
          <SelectTrigger id={progressId} className="h-9 w-full rounded-full sm:w-60" data-testid={`progress-${service.id}`}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {PROGRESS.map((p) => (
              <SelectItem key={p} value={p} data-testid={`progress-option-${p}`}>
                {t(`progress_${p}`)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {pending && (
          <p role="status" className="text-xs text-muted-foreground">
            {t("saving")}
          </p>
        )}
        {error && (
          <p role="alert" className="w-full text-sm text-destructive" data-testid="step-error">
            {error}
          </p>
        )}
      </div>

      {step.notes.length > 0 && (
        <ul className="space-y-1 text-sm text-muted-foreground sm:ps-9">
          {step.notes.map((note) => (
            <li key={note} className="flex gap-2">
              <span aria-hidden="true" className="mt-2 size-1 shrink-0 rounded-full bg-ghaf" />
              {note}
            </li>
          ))}
        </ul>
      )}

      <div className="sm:ps-9">
        <AuthorityNote notice={step.service_card.authority_notice} />
      </div>

      <footer className="flex flex-wrap items-start justify-between gap-3 border-t pt-4">
        <HandoffPanel step={step} disabled={locked} official={handoffs.official} support={handoffs.support} onRequest={onHandoff} />
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" size="sm" className="h-9 rounded-full px-4" onClick={onAskCoach} data-testid={`ask-coach-${service.id}`}>
            <MessageCircleQuestion aria-hidden="true" />
            {t("askCoach")}
          </Button>
          <Button variant="link" size="sm" asChild className="px-1 text-gulf">
            <Link href={`/services/${encodeURIComponent(service.id)}`}>{t("stepDetailsLink")}</Link>
          </Button>
        </div>
      </footer>
    </article>
  );
}
