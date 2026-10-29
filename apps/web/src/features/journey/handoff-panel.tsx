"use client";

import { ExternalLink, LifeBuoy, Loader2, Send } from "lucide-react";

import { errorMessageKey } from "@/components/layout/states";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";
import type { Handoff, JourneyStep } from "@/lib/api/types";
import { useLocale } from "@/lib/i18n/locale";

export type HandoffState = { status: "pending" } | { status: "ready"; handoff: Handoff } | { status: "error"; error: unknown };

function Result({ state, entity }: { state: HandoffState | undefined; entity: string }) {
  const { t } = useLocale();
  if (!state) return null;
  if (state.status === "pending") {
    return (
      <p role="status" className="flex items-center gap-1 text-sm">
        <Loader2 aria-hidden="true" className="size-4 animate-spin motion-reduce:animate-none" />
        {t("handoffPreparing")}
      </p>
    );
  }
  if (state.status === "error") {
    const unavailable = state.error instanceof ApiError && state.error.code === "HANDOFF_UNAVAILABLE";
    return (
      <p role="alert" className="rounded-xl bg-accent px-3 py-2 text-sm text-accent-foreground" data-testid="handoff-unavailable">
        {unavailable ? t("handoffUnavailable") : t(errorMessageKey(state.error))}
      </p>
    );
  }
  return (
    <div className="space-y-1 rounded-xl bg-[#e5f2eb] px-3 py-2.5 text-sm text-[#1d5a3e]" data-testid="handoff-ready">
      <p>{t("handoffReady", { entity })}</p>
      <a
        href={state.handoff.url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1 font-semibold text-gulf underline underline-offset-4"
      >
        {state.handoff.label} {t("opensInNewTab")}
        <ExternalLink aria-hidden="true" className="size-4" />
      </a>
    </div>
  );
}

export function HandoffPanel({
  step,
  disabled,
  official,
  support,
  onRequest,
}: {
  step: JourneyStep;
  disabled: boolean;
  official?: HandoffState;
  support?: HandoffState;
  onRequest: (kind: "official" | "support") => void;
}) {
  const { t } = useLocale();
  const { service } = step.service_card;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        <Button
          variant="default"
          size="sm"
          className="h-9 rounded-full px-4"
          disabled={disabled || official?.status === "pending"}
          onClick={() => onRequest("official")}
          data-testid={`handoff-official-${service.id}`}
        >
          <Send aria-hidden="true" className="rtl:-scale-x-100" />
          {t("continueOfficial")}
        </Button>
        {service.support_url && (
          <Button
            variant="outline"
            size="sm"
            className="h-9 rounded-full px-4"
            disabled={disabled || support?.status === "pending"}
            onClick={() => onRequest("support")}
          >
            <LifeBuoy aria-hidden="true" />
            {t("continueSupport")}
          </Button>
        )}
      </div>
      <Result state={official} entity={service.entity} />
      <Result state={support} entity={service.entity} />
    </div>
  );
}
