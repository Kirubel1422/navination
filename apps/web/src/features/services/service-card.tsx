"use client";

import { Building2, Info, MapPin, UserRoundPen } from "lucide-react";
import Link from "next/link";

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { openProfileSheet } from "@/features/profile/profile-events";
import type { MessageKey } from "@/lib/i18n/dictionaries";
import type { ServiceCard as ServiceCardData } from "@/lib/api/types";
import { useLocale } from "@/lib/i18n/locale";
import { cn } from "@/lib/utils";
import { OriginBadge, RelevanceBadge, VerificationBadge } from "./badges";
import { ReachSummary } from "@/features/reach/reach-summary";
import { SourcesList } from "./sources-list";

export function ReasonList({ card }: { card: ServiceCardData }) {
  return (
    <ul className="space-y-1.5 text-sm">
      {card.reasons.map((reason, index) => (
        <li key={index} className="flex gap-2">
          <span aria-hidden="true" className="mt-2 size-1.5 shrink-0 rounded-full bg-saffron" />
          <span>{reason.text}</span>
        </li>
      ))}
    </ul>
  );
}

export function MissingInfo({ card }: { card: ServiceCardData }) {
  const { t } = useLocale();
  if (card.missing_profile_fields.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl bg-[#e6eff8] px-3 py-2 text-sm text-[#1d5287]">
      <UserRoundPen aria-hidden="true" className="size-4 shrink-0" />
      <span className="font-medium">{t("missingInfo")}:</span>
      <span>{card.missing_profile_fields.map((field) => t(`field_${field}` as MessageKey)).join(", ")}</span>
      <Button variant="link" className="h-auto px-0 text-[#1d5287] underline" onClick={openProfileSheet}>
        {t("missingInfoAction")}
      </Button>
    </div>
  );
}

export function AuthorityNote({ notice }: { notice: string }) {
  const { t } = useLocale();
  return (
    <p className="flex items-start gap-2 text-sm text-muted-foreground">
      <Info aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      <span>
        <span className="font-medium text-foreground">{t("finalAuthority")}: </span>
        {notice}
      </span>
    </p>
  );
}

export function ServiceResultCard({
  card,
  selected,
  onSelectedChange,
  disabled,
}: {
  card: ServiceCardData;
  selected: boolean;
  onSelectedChange: (selected: boolean) => void;
  disabled?: boolean;
}) {
  const { t } = useLocale();
  const { service } = card;
  const checkboxId = `select-${service.id}`;
  return (
    <article
      className="surface service-result p-5 sm:p-6"
      data-selected={selected}
      data-testid={`service-card-${service.id}`}
      aria-labelledby={`title-${service.id}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <h3 id={`title-${service.id}`} className="t-head min-w-0 flex-1 basis-64">
          {service.title}
        </h3>
        <RelevanceBadge relevance={card.relevance} />
      </div>
      <p className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <Building2 aria-hidden="true" className="size-4 shrink-0" />
          <span className="sr-only">{t("serviceEntity")}: </span>
          {service.entity}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <MapPin aria-hidden="true" className="size-4 shrink-0" />
          <span className="sr-only">{t("serviceJurisdiction")}: </span>
          {service.jurisdiction}
        </span>
      </p>
      <p className="mt-3 line-clamp-3 max-w-[70ch] text-[0.95rem]">{service.summary}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <VerificationBadge status={service.verification_status} />
        <OriginBadge origin={service.origin} />
      </div>
      {card.missing_profile_fields.length > 0 && (
        <div className="mt-3">
          <MissingInfo card={card} />
        </div>
      )}
      <section aria-label={t("whyShown")} className="mt-4 space-y-2.5 rounded-2xl bg-salt p-4">
        <h4 className="t-label">{t("whyShown")}</h4>
        <ReasonList card={card} />
        <AuthorityNote notice={card.authority_notice} />
      </section>
      <div className="mt-4">
        <ReachSummary reach={card.reach} serviceId={service.id} serviceTitle={service.title} />
      </div>
      <Accordion type="single" collapsible className="mt-1">
        <AccordionItem value="sources" className="border-b-0">
          <AccordionTrigger className="py-2.5 text-sm">
            {t("sourcesHeading")} ({service.sources.length})
          </AccordionTrigger>
          <AccordionContent>
            <SourcesList sources={service.sources} />
          </AccordionContent>
        </AccordionItem>
      </Accordion>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t pt-4">
        <label
          htmlFor={checkboxId}
          className={cn(
            "inline-flex h-10 cursor-pointer items-center gap-2.5 rounded-full border px-4 text-sm font-medium transition-colors",
            selected ? "border-gulf bg-gulf text-white" : "bg-card hover:border-gulf",
          )}
        >
          <Checkbox
            id={checkboxId}
            checked={selected}
            disabled={disabled}
            onCheckedChange={(value) => onSelectedChange(value === true)}
            className={cn(selected && "border-white data-checked:border-white data-checked:bg-white data-checked:text-gulf")}
            data-testid={`select-${service.id}`}
          />
          <span>
            {t("selectService")}
            <span className="sr-only">: {service.title}</span>
          </span>
        </label>
        <Button variant="link" asChild className="px-0 text-gulf">
          <Link href={`/services/${encodeURIComponent(service.id)}`}>
            {t("viewDetails")}
            <span className="sr-only">: {service.title}</span>
          </Link>
        </Button>
      </div>
    </article>
  );
}
