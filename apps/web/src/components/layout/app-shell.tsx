"use client";

import { FlaskConical, Languages, Trash2 } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
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
import { Mark } from "./mark";

function SessionGate({ children }: { children: React.ReactNode }) {
  const { state, startNewSession, retryBootstrap } = useSession();
  const { t } = useLocale();
  const router = useRouter();
  const pathname = usePathname();

  // Open data is public: it never needs a guest session.
  if (pathname.startsWith("/data")) return <>{children}</>;

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
      <Tooltip>
        <TooltipTrigger asChild>
          <DialogTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="size-9 rounded-full text-muted-foreground hover:bg-[#fdf1f0] hover:text-destructive"
              aria-label={t("clearSession")}
              data-testid="clear-session-open"
            >
              <Trash2 aria-hidden="true" />
            </Button>
          </DialogTrigger>
        </TooltipTrigger>
        <TooltipContent>{t("clearSession")}</TooltipContent>
      </Tooltip>
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
      <header className="sticky top-0 z-40 border-b border-border/70 bg-salt/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center gap-x-3 px-4 py-2.5 sm:gap-x-6 sm:px-6 sm:py-3">
          <Link href="/" className="flex items-center gap-2.5 rounded-full focus-visible:ring-2 focus-visible:ring-ring">
            <Mark />
            <span className="text-[1.08rem] font-semibold tracking-[-0.01em] [font-variation-settings:'HEXP'_30]">NaviNation</span>
            <span className="sr-only">: {t("tagline")}</span>
          </Link>
          <div className="hidden lg:block lg:flex-1">
            <Suspense fallback={<div className="h-8" />}>
              <JourneyNavigation />
            </Suspense>
          </div>
          <nav aria-label="NaviNation" className="ms-auto flex shrink-0 items-center gap-0.5 sm:gap-1">
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
              className="h-9 rounded-full px-2.5 sm:px-3"
              lang={locale === "en" ? "ar" : "en"}
              aria-label={t("languageToggleLabel")}
              onClick={() => setLocale(locale === "en" ? "ar" : "en")}
              data-testid="language-toggle"
            >
              <Languages aria-hidden="true" className="max-sm:hidden" />
              {t("languageToggle")}
            </Button>
            <ProfileSheet />
            <ClearSessionButton />
          </nav>
        </div>
      </header>
      {/* On phones the route bar scrolls away so the sticky header stays one row. */}
      <div className="border-b border-border/70 px-4 py-2.5 lg:hidden">
        <Suspense fallback={<div className="h-6" />}>
          <JourneyNavigation />
        </Suspense>
      </div>
      <main id="main" tabIndex={-1} className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 focus:outline-none sm:px-6 sm:py-10">
        {/* The gate reads the path (public /data skips it), which needs a Suspense boundary. */}
        <Suspense fallback={<LoadingState label={t("loading")} />}>
          <SessionGate>{children}</SessionGate>
        </Suspense>
      </main>
      <footer className="mt-10">
        <div className="sadu-band opacity-90" aria-hidden="true" />
        <div className="bg-card">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6">
            <p className="max-w-2xl text-xs leading-5 text-muted-foreground">{t("footerDisclaimer")}</p>
            <Link href="/data" className="text-xs font-medium text-gulf underline decoration-ghaf underline-offset-2" data-testid="footer-open-data">
              {t("footerData")}
            </Link>
          </div>
        </div>
      </footer>
    </AnnouncerProvider>
  );
}
