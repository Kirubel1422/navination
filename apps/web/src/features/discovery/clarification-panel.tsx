"use client";

import { MessageCircleQuestion } from "lucide-react";
import { useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import type { Clarification } from "@/lib/api/types";
import { useLocale } from "@/lib/i18n/locale";

export function ClarificationPanel({
  clarification,
  pending,
  onAnswer,
}: {
  clarification: Clarification;
  pending: boolean;
  onAnswer: (optionId: string) => void;
}) {
  const { t } = useLocale();
  const [choice, setChoice] = useState<string>("");
  const base = useId();
  return (
    <section className="surface overflow-hidden" data-testid="clarification" aria-labelledby={`${base}-heading`}>
      <div className="flex items-center gap-3 border-b bg-accent px-6 py-4">
        <MessageCircleQuestion aria-hidden="true" className="size-5 text-saffron-ink" />
        <h2 id={`${base}-heading`} className="t-head text-accent-foreground">
          {t("clarificationHeading")}
        </h2>
      </div>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (choice) onAnswer(choice);
        }}
        className="space-y-5 p-6"
      >
        <fieldset className="space-y-3">
          <legend className="mb-3 text-[1.05rem] font-medium">{clarification.prompt}</legend>
          <RadioGroup value={choice} onValueChange={setChoice} className="gap-2">
            {clarification.options.map((option) => (
              <label
                key={option.id}
                htmlFor={`${base}-${option.id}`}
                className="flex cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 transition-colors hover:border-gulf has-[[data-state=checked]]:border-gulf has-[[data-state=checked]]:bg-secondary"
              >
                <RadioGroupItem value={option.id} id={`${base}-${option.id}`} />
                <span>{option.label}</span>
              </label>
            ))}
          </RadioGroup>
        </fieldset>
        <Button type="submit" className="h-11 rounded-full px-6" disabled={!choice || pending} data-testid="clarification-submit">
          {pending ? t("searching") : t("clarificationAction")}
        </Button>
      </form>
    </section>
  );
}
