"use client";

import { useMutation } from "@tanstack/react-query";
import { Check, ListChecks, RefreshCw, Route } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { AgentActivity } from "@/components/layout/agent-activity";
import { AgentLoader } from "@/components/layout/agent-loader";
import { useAnnounce } from "@/components/layout/announcer";
import { ErrorState } from "@/components/layout/states";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { AiChip } from "@/features/services/badges";
import { ServiceResultCard } from "@/features/services/service-card";
import { api } from "@/lib/api/endpoints";
import type { Discovery } from "@/lib/api/types";
import { useLocale } from "@/lib/i18n/locale";
import { useReadySession } from "@/lib/session/session-provider";
import { writeStored } from "@/lib/session/storage";
import { ClarificationPanel } from "./clarification-panel";
import { DiscoveryForm, SUPPORTED_EXAMPLES } from "./discovery-form";
import { saveDiscovery, usePreviousDiscovery, useStoredDiscovery, type StoredDiscovery } from "./discovery-store";
import { useDiscover } from "./use-discover";

function WhatChanged({ previous, current }: { previous: Discovery; current: Discovery }) {
  const { t } = useLocale();
  if (previous.context_revision === current.context_revision) return null;
  const before = new Map(previous.results.map((c) => [c.service.id, c.relevance]));
  const changes = current.results.filter((c) => before.has(c.service.id) && before.get(c.service.id) !== c.relevance);
  return (
    <Alert data-testid="what-changed">
      <RefreshCw aria-hidden="true" />
      <AlertTitle>{t("whatChangedHeading")}</AlertTitle>
      <AlertDescription>
        {changes.length === 0 ? (
          <p>{t("whatChangedNone")}</p>
        ) : (
          <ul className="list-disc ps-5">
            {changes.map((c) => (
              <li key={c.service.id}>
                {t("changedFromTo", {
                  title: c.service.title,
                  from: t(`relevance_${before.get(c.service.id)!}`),
                  to: t(`relevance_${c.relevance}`),
                })}
              </li>
            ))}
          </ul>
        )}
      </AlertDescription>
    </Alert>
  );
}

export function DiscoverView() {
  const { t, locale } = useLocale();
  const router = useRouter();
  const announce = useAnnounce();
  const { token, session } = useReadySession();
  const stored = useStoredDiscovery(session.id);
  const previous = usePreviousDiscovery(session.id);
  const discover = useDiscover();
  const createJourney = useMutation({
    mutationFn: () =>
      api.createJourney({ token }, { discovery_id: stored!.discovery.id, service_ids: stored!.selected }),
    onSuccess: (journey) => {
      writeStored("activeJourney", journey.id);
      router.push(`/journeys/${encodeURIComponent(journey.id)}`);
    },
  });

  const run = (query: string, optionId?: string) => {
    const current = stored?.discovery;
    discover.mutate(
      {
        query,
        clarification_answer:
          optionId && current?.clarification
            ? { discovery_id: current.id, question_id: current.clarification.id, option_id: optionId }
            : null,
      },
      {
        onSuccess: (discovery) => announce(discovery.interpreted_need),
      },
    );
  };

  if (!stored) {
    return (
      <div className="surface mx-auto max-w-md space-y-4 p-8 text-center">
        <p className="t-head">{t("noDiscovery")}</p>
        <Button asChild className="h-10 rounded-full px-5">
          <Link href="/">{t("home")}</Link>
        </Button>
      </div>
    );
  }

  const { discovery } = stored;
  const profileOutdated = discovery.context_revision !== session.context_revision;
  const localeOutdated = stored.locale !== locale;
  const setSelected = (serviceId: string, selected: boolean) => {
    const next: StoredDiscovery = {
      ...stored,
      selected: selected
        ? [...new Set([...stored.selected, serviceId])]
        : stored.selected.filter((id) => id !== serviceId),
    };
    saveDiscovery(next);
  };

  return (
    <div className="grid grid-cols-1 items-start gap-x-10 gap-y-8 lg:grid-cols-[minmax(0,21rem)_minmax(0,1fr)]">
      <aside className="min-w-0 space-y-5 lg:sticky lg:top-28" aria-labelledby="interpreted">
        <section className="space-y-3">
          <h2 id="interpreted" className="t-label">
            {t("interpretedNeed")}
          </h2>
          <p className="t-title" data-testid="interpreted-need">
            {discovery.interpreted_need}
          </p>
          <AiChip>{t("aiInterpretation")}</AiChip>
          <AgentActivity steps={discovery.agent_steps} />
        </section>
        <DiscoveryForm
          key={discovery.id}
          compact
          defaultQuery={discovery.query}
          pending={discover.isPending}
          onSubmit={(query) => run(query)}
        />
        {discovery.status === "ready" && discovery.notices.length > 0 && (
          <ul className="space-y-1.5 text-xs leading-5 text-muted-foreground">
            {discovery.notices.map((n) => (
              <li key={n} className="flex gap-2">
                <span aria-hidden="true" className="mt-1.5 size-1 shrink-0 rounded-full bg-ghaf" />
                {n}
              </li>
            ))}
          </ul>
        )}
      </aside>

      <div className="min-w-0 space-y-6">
        {discover.isPending && (
          <p role="status" className="sr-only" data-testid="agent-working">
            {t("agentWorking")}
          </p>
        )}
        {discover.error ? <ErrorState error={discover.error} onRetry={() => run(discovery.query)} /> : null}

        {(profileOutdated || localeOutdated) && (
          <div
            data-testid="results-outdated"
            className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-accent px-4 py-3 text-accent-foreground"
          >
            <p className="flex items-center gap-2 text-sm font-medium">
              <RefreshCw aria-hidden="true" className="size-4 shrink-0" />
              {profileOutdated ? t("resultsOutdated") : t("localeOutdated")}
            </p>
            <Button
              size="sm"
              className="h-9 rounded-full px-4"
              disabled={discover.isPending}
              onClick={() => run(discovery.query)}
              data-testid="update-results"
            >
              {profileOutdated ? t("updateResults") : t("searchAgainInLanguage")}
            </Button>
          </div>
        )}

        {discovery.status === "needs_clarification" && discovery.clarification && (
          <ClarificationPanel
            clarification={discovery.clarification}
            pending={discover.isPending}
            onAnswer={(optionId) => run(discovery.query, optionId)}
          />
        )}

        {discovery.status === "no_match" && (
          <section aria-labelledby="no-match" className="surface space-y-4 p-6 sm:p-8" data-testid="no-match">
            {/* eslint-disable-next-line @next/next/no-img-element -- pixel-art asset */}
            <img src="/art/sun.png" alt="" width={48} height={48} className="pixel" />
            <h2 id="no-match" className="t-title">
              {t("noMatchHeading")}
            </h2>
            <p className="text-muted-foreground">{t("noMatchBody")}</p>
            {discovery.notices.length > 0 && (
              <ul className="space-y-1 text-sm">
                {discovery.notices.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            )}
            <div className="flex flex-wrap gap-2">
              {SUPPORTED_EXAMPLES[locale].map((example) => (
                <Button
                  key={example}
                  variant="outline"
                  className="h-auto min-h-10 justify-start rounded-full px-4 py-2 text-start whitespace-normal"
                  onClick={() => run(example)}
                >
                  {example}
                </Button>
              ))}
            </div>
          </section>
        )}

        {discovery.status === "ready" && (
          <section aria-labelledby="results-heading" className="space-y-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 id="results-heading" className="t-head">
                {t("resultsHeading")}
              </h2>
              <p className="text-sm text-muted-foreground">{t("selectionHint")}</p>
            </div>
            {previous && <WhatChanged previous={previous.discovery} current={discovery} />}
            <ol className="stop-list">
              {discovery.results.map((card, index) => {
                const selected = stored.selected.includes(card.service.id);
                return (
                  <li key={card.service.id} data-selected={selected}>
                    <span className="stop-dot text-xs font-semibold text-muted-foreground" aria-hidden="true">
                      {selected ? <Check className="size-3.5" strokeWidth={3} /> : index + 1}
                    </span>
                    <ServiceResultCard
                      card={card}
                      selected={selected}
                      onSelectedChange={(value) => setSelected(card.service.id, value)}
                      disabled={createJourney.isPending}
                    />
                  </li>
                );
              })}
            </ol>
            <div className="sticky bottom-4 z-10 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-full bg-ink py-2 ps-5 pe-2 text-white shadow-[0_20px_40px_-20px_rgb(16_37_45/0.7)]">
              <span aria-live="polite" className="flex items-center gap-2 text-sm font-medium">
                <Route aria-hidden="true" className="size-4 text-saffron" />
                {t("selectedCount", { count: stored.selected.length })}
              </span>
              {(stored.selected.length === 0 || profileOutdated) && (
                <span className="hidden text-xs text-white/70 sm:inline">
                  {profileOutdated ? t("discoveryStale") : t("selectAtLeastOne")}
                </span>
              )}
              <Button
                size="lg"
                className="ms-auto h-11 rounded-full bg-saffron px-5 text-ink hover:bg-[#f0b55e] disabled:bg-white/20 disabled:text-white/70 disabled:opacity-100"
                disabled={stored.selected.length === 0 || createJourney.isPending || profileOutdated}
                onClick={() => createJourney.mutate()}
                data-testid="create-plan"
              >
                <ListChecks aria-hidden="true" />
                {createJourney.isPending ? t("creatingPlan") : t("createPlan")}
              </Button>
            </div>
            {createJourney.error ? <ErrorState error={createJourney.error} /> : null}
          </section>
        )}
      </div>

      <AgentLoader open={discover.isPending} runId={discover.submittedAt} task="search" />
      <AgentLoader open={createJourney.isPending} runId={createJourney.submittedAt} task="plan" />
    </div>
  );
}
