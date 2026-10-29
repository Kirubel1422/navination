"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Building2, Clock3, ExternalLink, MapPin, Wallet } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { ErrorState, LoadingState } from "@/components/layout/states";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/query-keys";
import { useLocale } from "@/lib/i18n/locale";
import { useReadySession } from "@/lib/session/session-provider";
import { OriginBadge, RelevanceBadge, UnconfirmedValue, VerificationBadge } from "./badges";
import { RequirementList } from "./requirement-list";
import { MissingInfo, ReasonList } from "./service-card";
import { SourcesList } from "./sources-list";

export function ServiceDetailView() {
  const params = useParams<{ serviceId: string }>();
  const serviceId = decodeURIComponent(params.serviceId);
  const { t } = useLocale();
  const { token, session } = useReadySession();
  const query = useQuery({
    queryKey: queryKeys.service(session.id, session.locale, session.context_revision, serviceId),
    queryFn: ({ signal }) => api.getService({ token, signal }, serviceId),
  });

  if (query.isPending) return <LoadingState label={t("loading")} />;
  if (query.error) {
    const notFound = query.error instanceof ApiError && query.error.status === 404;
    return notFound ? (
      <p role="alert">{t("serviceNotFound")}</p>
    ) : (
      <ErrorState error={query.error} onRetry={() => query.refetch()} />
    );
  }
  const card = query.data;
  const { service } = card;
  const facts = [
    { icon: Building2, label: t("serviceEntity"), value: service.entity },
    { icon: MapPin, label: t("serviceJurisdiction"), value: service.jurisdiction },
    { icon: Wallet, label: t("serviceFees"), value: service.fee_text },
    { icon: Clock3, label: t("serviceTime"), value: service.processing_time_text },
  ];
  const linkable =
    (service.verification_status === "verified" || service.origin === "ai_web") && (service.official_url || service.support_url);
  return (
    <article className="mx-auto max-w-4xl space-y-8" aria-labelledby="service-title" data-testid="service-detail">
      <Button variant="link" asChild className="h-auto px-0 text-muted-foreground hover:text-foreground">
        <Link href="/discover">
          <ArrowLeft aria-hidden="true" className="rtl:rotate-180" />
          {t("backToSearch")}
        </Link>
      </Button>
      <header className="space-y-4">
        <h1 id="service-title" className="t-title max-w-[26ch]">
          {service.title}
        </h1>
        <div className="flex flex-wrap gap-2">
          <RelevanceBadge relevance={card.relevance} />
          <VerificationBadge status={service.verification_status} />
          <OriginBadge origin={service.origin} />
        </div>
        <p className="max-w-[68ch] text-[1.05rem] text-muted-foreground">{service.summary}</p>
      </header>

      <dl className="surface grid overflow-hidden sm:grid-cols-2 lg:grid-cols-4">
        {facts.map(({ icon: Icon, label, value }) => (
          <div key={label} className="space-y-1 border-b p-5 last:border-b-0 sm:[&:nth-child(odd)]:border-e lg:border-e lg:border-b-0 lg:last:border-e-0">
            <dt className="t-label flex items-center gap-1.5">
              <Icon aria-hidden="true" className="size-4 text-gulf" />
              {label}
            </dt>
            <dd className="text-[0.95rem] font-medium">{value ?? <UnconfirmedValue />}</dd>
          </div>
        ))}
      </dl>

      <div className="grid gap-x-10 gap-y-8 md:grid-cols-2">
        <section aria-labelledby="why-heading" className="space-y-3">
          <h2 id="why-heading" className="t-head">
            {t("whyShown")}
          </h2>
          <ReasonList card={card} />
          <MissingInfo card={card} />
        </section>
        <section aria-labelledby="criteria-heading" className="space-y-3">
          <h2 id="criteria-heading" className="t-head">
            {t("serviceCriteria")}
          </h2>
          <RequirementList items={service.eligibility_criteria} />
        </section>
        <section aria-labelledby="docs-heading" className="space-y-3">
          <h2 id="docs-heading" className="t-head">
            {t("serviceDocuments")}
          </h2>
          <RequirementList items={service.documents} />
        </section>
        <section aria-labelledby="authority-heading" className="space-y-3">
          <h2 id="authority-heading" className="t-head">
            {t("finalAuthority")}
          </h2>
          <p className="text-sm">{card.authority_notice}</p>
        </section>
      </div>

      <section aria-labelledby="continue-heading" className="overflow-hidden rounded-[1.5rem] bg-ink text-white">
        <div className="sadu-band" aria-hidden="true" />
        <div className="space-y-3 p-6 sm:p-7">
          <h2 id="continue-heading" className="t-head">
            {t("continueOptions")}
          </h2>
          <p className="text-sm text-white/75">{t("officialSiteNote")}</p>
          {linkable ? (
            <ul className="flex flex-wrap gap-2">
              {service.official_url && (
                <li>
                  <a
                    href={service.official_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex h-10 items-center gap-2 rounded-full bg-saffron px-4 text-sm font-semibold text-ink hover:bg-[#f0b55e]"
                  >
                    {t("officialLinkLabel")}: {service.entity} <span className="sr-only">{t("opensInNewTab")}</span>
                    <ExternalLink aria-hidden="true" className="size-4" />
                  </a>
                </li>
              )}
              {service.support_url && (
                <li>
                  <a
                    href={service.support_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex h-10 items-center gap-2 rounded-full bg-white/10 px-4 text-sm font-medium text-white ring-1 ring-white/25 hover:bg-white/15"
                  >
                    {t("supportLinkLabel")} <span className="sr-only">{t("opensInNewTab")}</span>
                    <ExternalLink aria-hidden="true" className="size-4" />
                  </a>
                </li>
              )}
            </ul>
          ) : (
            <p className="text-sm">{t("handoffUnavailable")}</p>
          )}
        </div>
      </section>

      <section aria-labelledby="sources-heading" className="space-y-3">
        <h2 id="sources-heading" className="t-head">
          {t("sourcesHeading")}
        </h2>
        <SourcesList sources={service.sources} />
      </section>
    </article>
  );
}
