"use client";

import { Mic, MicOff, Square } from "lucide-react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useLocale } from "@/lib/i18n/locale";
import { cn } from "@/lib/utils";
import type { useVoiceInput } from "@/lib/voice";

type Voice = ReturnType<typeof useVoiceInput>;

/** Mic toggle for dictation. Hidden reasons (unsupported, blocked) are explained on hover/focus. */
export function VoiceButton({ voice, size = "md", testId }: { voice: Voice; size?: "sm" | "md"; testId?: string }) {
  const { t } = useLocale();
  const label = !voice.supported ? t("voiceUnsupported") : voice.listening ? t("voiceStop") : t("voiceStart");
  const box = size === "sm" ? "size-9" : "size-12";
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={label}
          aria-pressed={voice.listening}
          aria-disabled={!voice.supported}
          data-testid={testId}
          onClick={() => (voice.supported ? (voice.listening ? voice.stop() : voice.start()) : undefined)}
          className={cn(
            "relative grid shrink-0 place-items-center rounded-full border transition-colors",
            box,
            voice.listening ? "border-saffron bg-saffron text-ink" : "bg-card text-gulf hover:border-gulf hover:bg-secondary",
            !voice.supported && "cursor-not-allowed text-muted-foreground opacity-70",
          )}
        >
          {voice.listening && (
            <>
              <span aria-hidden="true" className="voice-ring absolute inset-0 rounded-full" />
              <span aria-hidden="true" className="voice-ring voice-ring-late absolute inset-0 rounded-full" />
            </>
          )}
          {voice.listening ? (
            <Square aria-hidden="true" className="relative size-3.5 fill-current" />
          ) : voice.supported ? (
            <Mic aria-hidden="true" className={size === "sm" ? "size-4" : "size-5"} />
          ) : (
            <MicOff aria-hidden="true" className="size-4" />
          )}
        </button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}

/** One line under an input: "Listening…" or what went wrong. */
export function VoiceStatus({ voice }: { voice: Voice }) {
  const { t } = useLocale();
  if (voice.listening) {
    return (
      <p role="status" className="flex items-center gap-2 text-xs font-medium text-saffron-ink">
        <span className="voice-bars" aria-hidden="true">
          <span />
          <span />
          <span />
          <span />
        </span>
        {t("voiceListening")}
      </p>
    );
  }
  if (!voice.error) return null;
  return (
    <p role="alert" className="text-xs text-destructive">
      {voice.error === "denied" ? t("voiceDenied") : t("voiceError")}
    </p>
  );
}
