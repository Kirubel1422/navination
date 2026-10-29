"use client";

import {
  AlertCircle,
  Ban,
  BadgeCheck,
  Bot,
  CheckCircle2,
  CircleHelp,
  FlaskConical,
  HelpCircle,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";

import type { JourneyStep, Relevance, Service, VerificationStatus } from "@/lib/api/types";
import { useLocale } from "@/lib/i18n/locale";
import { cn } from "@/lib/utils";

type Availability = JourneyStep["availability"];

/** One tone per meaning, used the same way on every page. */
const TONES = {
  gulf: "bg-[#e1eef0] text-[#0b4d59] ring-[#0e6170]/25 [--glyph:#0e6170]",
  mangrove: "bg-[#e5f2eb] text-[#1d5a3e] ring-[#2d7a57]/25 [--glyph:#2d7a57]",
  lagoon: "bg-[#e6eff8] text-[#1d5287] ring-[#2a6fb0]/25 [--glyph:#2a6fb0]",
  saffron: "bg-[#fcefd9] text-[#7a4d0c] ring-[#e9a23b]/45 [--glyph:#c98316]",
  dusk: "bg-[#efeaf7] text-[#4b357c] ring-[#6b4fa0]/25 [--glyph:#6b4fa0]",
  slate: "bg-[#eaefed] text-[#3d5356] ring-[#9db8b4]/60 [--glyph:#4b6265]",
} as const;

export type Tone = keyof typeof TONES;

/** Status is always conveyed by icon + text, never by colour alone. */
export function StatusChip({
  tone,
  icon: Icon,
  children,
  className,
  ...props
}: {
  tone: Tone;
  icon: LucideIcon;
  children: React.ReactNode;
  className?: string;
} & Omit<React.ComponentProps<"span">, "children">) {
  return (
    <span
      className={cn(
        "inline-flex min-h-6 max-w-full items-center gap-1.5 rounded-full py-0.5 ps-0.5 pe-2.5 text-[0.78rem] leading-snug font-medium ring-1 ring-inset",
        TONES[tone],
        className,
      )}
      {...props}
    >
      <span aria-hidden="true" className="grid size-5 shrink-0 place-items-center rounded-full bg-white/80">
        <Icon className="size-3.5 text-(--glyph)" strokeWidth={2.2} />
      </span>
      <span className="min-w-0">{children}</span>
    </span>
  );
}

const RELEVANCE: Record<Relevance, { icon: LucideIcon; tone: Tone }> = {
  potentially_relevant: { icon: BadgeCheck, tone: "mangrove" },
  more_information_needed: { icon: CircleHelp, tone: "lagoon" },
  criterion_mismatch: { icon: AlertCircle, tone: "saffron" },
};

export function RelevanceBadge({ relevance }: { relevance: Relevance }) {
  const { t } = useLocale();
  const { icon, tone } = RELEVANCE[relevance];
  return (
    <StatusChip tone={tone} icon={icon} data-relevance={relevance}>
      {t(`relevance_${relevance}`)}
    </StatusChip>
  );
}

const VERIFICATION: Record<VerificationStatus, { icon: LucideIcon; tone: Tone }> = {
  verified: { icon: ShieldCheck, tone: "gulf" },
  needs_review: { icon: ShieldAlert, tone: "saffron" },
  demo: { icon: FlaskConical, tone: "slate" },
};

export function VerificationBadge({ status }: { status: VerificationStatus }) {
  const { t } = useLocale();
  const { icon, tone } = VERIFICATION[status];
  return (
    <StatusChip tone={tone} icon={icon} data-verification={status}>
      {t(`verification_${status}`)}
    </StatusChip>
  );
}

/** Marks services the AI agent found on an official website during this session. */
export function OriginBadge({ origin }: { origin: Service["origin"] }) {
  const { t } = useLocale();
  if (origin !== "ai_web") return null;
  return (
    <StatusChip tone="dusk" icon={Sparkles} data-testid="origin-ai-web">
      {t("origin_ai_web")}
    </StatusChip>
  );
}

const AVAILABILITY: Record<Availability, { icon: LucideIcon; tone: Tone }> = {
  ready: { icon: CheckCircle2, tone: "mangrove" },
  blocked: { icon: Ban, tone: "slate" },
  review_needed: { icon: TriangleAlert, tone: "saffron" },
};

export function AvailabilityBadge({ availability }: { availability: Availability }) {
  const { t } = useLocale();
  const { icon, tone } = AVAILABILITY[availability];
  return (
    <StatusChip tone={tone} icon={icon} data-testid="availability">
      {t(`availability_${availability}`)}
    </StatusChip>
  );
}

export function AiChip({ children, ...props }: { children: React.ReactNode } & React.ComponentProps<"span">) {
  return (
    <StatusChip tone="dusk" icon={Bot} {...props}>
      {children}
    </StatusChip>
  );
}

export function UnconfirmedValue() {
  const { t } = useLocale();
  return (
    <span className="inline-flex items-center gap-1 text-muted-foreground italic">
      <HelpCircle aria-hidden="true" className="size-3.5" />
      {t("notConfirmed")}
    </span>
  );
}
