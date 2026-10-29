"use client";

import { AlertTriangle, RefreshCw, WifiOff } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import type { MessageKey } from "@/lib/i18n/dictionaries";
import { useLocale } from "@/lib/i18n/locale";

export function errorMessageKey(error: unknown): MessageKey {
  const code = error instanceof ApiError ? error.code : "INTERNAL_ERROR";
  return `error_${code}` as MessageKey;
}

/** Localized error text that keeps the diagnostic request ID visible. */
export function ErrorState({
  error,
  onRetry,
  title,
}: {
  error: unknown;
  onRetry?: () => void;
  title?: string;
}) {
  const { t } = useLocale();
  const apiError = error instanceof ApiError ? error : null;
  const connection = apiError && ["NETWORK_ERROR", "TIMEOUT"].includes(apiError.code);
  const aiDown = apiError?.code === "SERVICE_UNAVAILABLE";
  const Icon = connection ? WifiOff : AlertTriangle;
  const known = apiError && (`error_${apiError.code}` as MessageKey);
  return (
    <Alert variant="destructive" data-testid="error-state" className="rounded-2xl border-destructive/25 bg-[#fdf1f0] px-4 py-3.5">
      <Icon aria-hidden="true" />
      <AlertTitle>
        {title ?? (connection ? t("connectionErrorTitle") : aiDown ? t("aiUnavailableTitle") : t("genericErrorTitle"))}
      </AlertTitle>
      <AlertDescription>
        <p>
          {connection
            ? apiError.code === "TIMEOUT"
              ? t("timeoutErrorBody")
              : t("connectionErrorBody")
            : aiDown
              ? t("aiUnavailableBody")
              : known
              ? t(known)
              : t("error_INTERNAL_ERROR")}
        </p>
        {apiError?.requestId && (
          <p className="text-xs opacity-80">
            {t("requestId")}: <span dir="ltr">{apiError.requestId}</span>
          </p>
        )}
        {onRetry && (
          <Button variant="outline" size="sm" className="mt-2 h-8 rounded-full bg-card" onClick={onRetry}>
            <RefreshCw aria-hidden="true" />
            {t("retry")}
          </Button>
        )}
      </AlertDescription>
    </Alert>
  );
}

export function LoadingState({ label }: { label: string }) {
  return (
    <div role="status" aria-live="polite" className="space-y-4" data-testid="loading-state">
      <span className="sr-only">{label}</span>
      <Skeleton className="h-4 w-32 rounded-full" />
      <Skeleton className="h-10 w-2/3 rounded-xl" />
      <Skeleton className="h-28 w-full rounded-[1.25rem]" />
      <Skeleton className="h-28 w-full rounded-[1.25rem]" />
    </div>
  );
}
