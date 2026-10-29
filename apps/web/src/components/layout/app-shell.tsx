"use client";

import { FlaskConical, Languages, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Suspense, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { ProfileSheet } from "@/features/profile/profile-sheet";
import { API_MODE } from "@/lib/config";
import { useLocale } from "@/lib/i18n/locale";
import { useSession } from "@/lib/session/session-provider";
import { AnnouncerProvider } from "./announcer";
import { ErrorState, LoadingState } from "./states";
import { JourneyNavigation } from "./journey-navigation";

function SessionGate({ children }: { children: React.ReactNode }) {
  const { state, startNewSession, retryBootstrap } = useSession();
  const { t } = useLocale();
  const router = useRouter();

  if (state.status === "loading") return <LoadingState label={t("sessionStarting")} />;
  if (state.status === "error") return <ErrorState error={state.error} onRetry={retryBootstrap} />;
  if (state.status === "expired" || state.status === "cleared") {
    const expired = state.status === "expired";
    return (
      <section
        aria-labelledby="session-ended"
        className="surface mx-auto mt-6 max-w-lg overflow-hidden"
        data-testid={expired ? "session-expired" : "session-cleared"}
      >
        <div className="sadu-band" aria-hidden="true" />
        <div className="flex flex-col items-start gap-4 p-7">
          {/* eslint-disable-next-line @next/next/no-img-element -- pixel-art asset */}
          <img src="/art/sun.png" alt="" width={56} height={56} className="pixel" />
          <h1 id="session-ended" className="t-title">
            {expired ? t("sessionExpiredTitle") : t("sessionClearedTitle")}
          </h1>
          <p className="text-muted-foreground">{expired ? t("sessionExpiredBody") : t("sessionClearedBody")}</p>
          <Button
            size="lg"
            className="h-11 rounded-full px-5"
            onClick={async () => {
              await startNewSession();
              router.push("/");
            }}
          >
            {t("sessionStartNew")}
          </Button>
        </div>
      </section>
    );
  }
  return <>{children}</>;
}

function ClearSessionButton() {
  const { state, clearSession } = useSession();
  const { t } = useLocale();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  if (state.status !== "ready") return null;
  return (
    <Dialog onOpenChange={() => setError(null)}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm" className="text-muted-foreground" data-testid="clear-session-open">
          <Trash2 aria-hidden="true" />
          {t("clearSession")}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("clearConfirmTitle")}</DialogTitle>
          <DialogDescription>{t("clearConfirmBody")}</DialogDescription>
        </DialogHeader>
        {error ? <ErrorState error={error} /> : null}
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline">{t("cancel")}</Button>
          </DialogClose>
          <Button
            variant="destructive"
            disabled={busy}
            data-testid="clear-session-confirm"
            onClick={async () => {
              setBusy(true);
              try {
                await clearSession();
                router.push("/");
              } catch (err) {
                setError(err);
              } finally {
                setBusy(false);
              }
            }}
          >
            {t("clearConfirmAction")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Mark() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" className="size-8 shrink-0">
      <circle cx="16" cy="16" r="15" fill="#0e6170" />
      <path d="M4 22c6 0 8-9 14-9s8-4 11-4" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" />
      <circle cx="18" cy="13" r="3.6" fill="#e9a23b" stroke="#fff" strokeWidth="1.6" />
    </svg>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { t, locale, setLocale } = useLocale();
  return (
    <AnnouncerProvider>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:start-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-background focus:px-4 focus:py-2 focus:ring-2 focus:ring-ring"
      >
        {t("skipToContent")}
      </a>
      <header className="z-40 border-b border-border/70 bg-salt/90 backdrop-blur-md lg:sticky lg:top-0">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
          <Link href="/" className="flex items-center gap-2.5 rounded-full focus-visible:ring-2 focus-visible:ring-ring">
            <Mark />
            <span className="text-[1.08rem] font-semibold tracking-[-0.01em] [font-variation-settings:'HEXP'_30]">NaviNation</span>
            <span className="sr-only">: {t("tagline")}</span>
          </Link>
          <div className="order-3 w-full lg:order-none lg:w-auto lg:flex-1">
            <Suspense fallback={<div className="h-8" />}>
              <JourneyNavigation />
            </Suspense>
          </div>
          <nav aria-label="NaviNation" className="ms-auto flex shrink-0 items-center gap-1">
            {API_MODE === "mock" && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <span
                    className="inline-flex h-7 items-center gap-1 rounded-full bg-accent px-2.5 text-xs font-medium text-accent-foreground"
                    data-testid="demo-indicator"
                    tabIndex={0}
                  >
                    <FlaskConical aria-hidden="true" className="size-3.5" />
                    <span className="max-sm:sr-only">{t("demoData")}</span>
                  </span>
                </TooltipTrigger>
                <TooltipContent>{t("demoDataDescription")}</TooltipContent>
              </Tooltip>
            )}
            <Button
              variant="ghost"
              size="sm"
              className="h-9 rounded-full px-3"
              lang={locale === "en" ? "ar" : "en"}
              aria-label={t("languageToggleLabel")}
              onClick={() => setLocale(locale === "en" ? "ar" : "en")}
              data-testid="language-toggle"
            >
              <Languages aria-hidden="true" />
              {t("languageToggle")}
            </Button>
            <ProfileSheet />
          </nav>
        </div>
      </header>
      <main id="main" tabIndex={-1} className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 focus:outline-none sm:px-6 sm:py-10">
        <SessionGate>{children}</SessionGate>
      </main>
      <footer className="mt-10">
        <div className="sadu-band opacity-90" aria-hidden="true" />
        <div className="bg-card">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6">
            <p className="max-w-2xl text-xs leading-5 text-muted-foreground">{t("footerDisclaimer")}</p>
            <ClearSessionButton />
          </div>
        </div>
      </footer>
    </AnnouncerProvider>
  );
}
