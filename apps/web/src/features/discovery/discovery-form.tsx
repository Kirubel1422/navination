"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, LockKeyhole, Search } from "lucide-react";
import { useId } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { LocationChip } from "@/components/layout/location-chip";
import { VoiceButton, VoiceStatus } from "@/components/layout/voice-button";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useLocale } from "@/lib/i18n/locale";
import { cn } from "@/lib/utils";
import { useVoiceInput } from "@/lib/voice";

const schema = z.object({
  query: z.string().trim().min(1, "queryRequired").max(2000, "queryTooLong"),
});
type Values = z.infer<typeof schema>;

export function DiscoveryForm({
  defaultQuery = "",
  pending,
  onSubmit,
  compact = false,
}: {
  defaultQuery?: string;
  pending: boolean;
  onSubmit: (query: string) => void;
  compact?: boolean;
}) {
  const { t, locale } = useLocale();
  // Unique per instance: hidden (preserved) pages keep their own copy of this form in the DOM.
  const id = useId();
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { query: defaultQuery } });
  const error = form.formState.errors.query?.message;
  const submit = form.handleSubmit((values) => onSubmit(values.query.trim()));
  // Speak instead of typing: words appear as they are heard, then the search runs.
  const voice = useVoiceInput({
    locale,
    onText: (text) => form.setValue("query", text, { shouldValidate: false }),
    onFinal: (text) => {
      form.setValue("query", text);
      if (!pending) void submit();
    },
  });
  return (
    <form onSubmit={submit} noValidate data-testid="discovery-form">
      <div
        className={cn(
          "surface group/composer transition-shadow focus-within:border-gulf focus-within:shadow-[0_0_0_4px_rgb(14_97_112/0.12)]",
          compact ? "rounded-2xl" : "rounded-[1.75rem] shadow-[0_18px_50px_-28px_rgb(16_37_45/0.45)]",
          error && "border-destructive",
        )}
      >
        <Label htmlFor={`${id}-query`} className="sr-only">
          {t("queryLabel")}
        </Label>
        <textarea
          id={`${id}-query`}
          rows={compact ? 2 : 3}
          maxLength={2000}
          placeholder={t("queryPlaceholder")}
          aria-describedby={error ? `${id}-hint ${id}-error` : `${id}-hint`}
          aria-invalid={Boolean(error)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) void submit();
          }}
          className={cn(
            "block w-full resize-none bg-transparent outline-none placeholder:text-muted-foreground/70 focus-visible:outline-none",
            compact ? "px-4 pt-3 text-base leading-7" : "px-5 pt-5 text-[1.15rem] leading-8 sm:px-6",
          )}
          {...form.register("query")}
        />
        <div className={cn("flex flex-wrap items-center justify-between gap-x-3 gap-y-2", compact ? "px-3 pb-3" : "px-4 pb-4 sm:px-5")}>
          <div className="flex min-w-0 flex-col gap-1.5 ps-1">
            <VoiceStatus voice={voice} />
            {!voice.listening && !voice.error && (
              <p id={`${id}-hint`} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <LockKeyhole aria-hidden="true" className="size-3.5 shrink-0" />
                {t("queryHint")}
              </p>
            )}
            <LocationChip />
          </div>
          <div className="ms-auto flex items-center gap-2">
            <VoiceButton voice={voice} size={compact ? "sm" : "md"} testId="voice-search" />
            <Button
            type="submit"
            size="lg"
            className={cn("rounded-full", compact ? "h-9 px-4" : "h-12 px-6 text-[0.95rem]")}
            disabled={pending}
            data-testid="search-submit"
          >
            {pending ? <Loader2 aria-hidden="true" className="animate-spin motion-reduce:animate-none" /> : <Search aria-hidden="true" />}
            {pending ? t("searching") : t("search")}
          </Button>
          </div>
        </div>
      </div>
      {error && (
        <p id={`${id}-error`} role="alert" className="mt-2 ps-2 text-sm text-destructive">
          {t(error as "queryRequired" | "queryTooLong")}
        </p>
      )}
    </form>
  );
}

export const SUPPORTED_EXAMPLES = {
  // The demo persona first: expat parents of a newborn in Umm Al Quwain.
  en: [
    "We just had a baby in Umm Al Quwain. What do we need to do?",
    "I recently arrived and need my overseas degree recognized",
    "How do I get my foreign high school certificate equalised?",
  ],
  ar: [
    "رزقنا بمولود جديد في أم القيوين، ما الخطوات المطلوبة؟",
    "وصلت حديثاً وأحتاج إلى الاعتراف بشهادتي الجامعية من الخارج",
  ],
} as const;
