"use client";

import { useId } from "react";

import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import type { DocumentStatus, JourneyStep } from "@/lib/api/types";
import { useLocale } from "@/lib/i18n/locale";

const STATUSES: DocumentStatus[] = ["have", "missing", "unknown"];

export function DocumentChecklist({
  step,
  disabled,
  onChange,
}: {
  step: JourneyStep;
  disabled: boolean;
  onChange: (documentId: string, status: DocumentStatus) => void;
}) {
  const { t } = useLocale();
  const base = useId();
  const documents = step.checklist;
  if (documents.length === 0) return <p className="text-sm text-muted-foreground italic">{t("noDocuments")}</p>;
  const statusOf = new Map(step.document_progress.map((d) => [d.document_id, d.status]));
  return (
    <div className="space-y-2">
      <ul className="divide-y rounded-2xl border">
        {documents.map((doc) => {
          const status = statusOf.get(doc.id) ?? "unknown";
          return (
            <li key={doc.id} data-status={status}>
              <fieldset className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-3" data-testid={`doc-${doc.id}`}>
                <legend className="float-start flex min-w-0 flex-1 basis-56 items-start gap-2 text-sm">
                  <span
                    aria-hidden="true"
                    className={`mt-1.5 size-2 shrink-0 rounded-full ${status === "have" ? "bg-mangrove" : status === "missing" ? "bg-saffron" : "bg-ghaf"}`}
                  />
                  <span>{doc.text}</span>
                </legend>
                <RadioGroup
                  value={status}
                  onValueChange={(value) => onChange(doc.id, value as DocumentStatus)}
                  disabled={disabled}
                  className="segmented"
                >
                  {STATUSES.map((option) => (
                    <div key={option}>
                      <RadioGroupItem value={option} id={`${base}-${doc.id}-${option}`} className="size-3.5" />
                      <Label htmlFor={`${base}-${doc.id}-${option}`} className="cursor-pointer font-normal">
                        {t(`doc_${option}`)}
                      </Label>
                    </div>
                  ))}
                </RadioGroup>
                {doc.source_ids.length === 0 && (
                  <p className="w-full ps-4 text-xs text-saffron-ink">{t("checklistUncited")}</p>
                )}
              </fieldset>
            </li>
          );
        })}
      </ul>
      <p className="text-xs text-muted-foreground">{t("documentsNote")}</p>
    </div>
  );
}
