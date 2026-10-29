"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

import { DirectionProvider } from "@/components/ui/direction";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ApiError } from "@/lib/api/client";
import { LocaleProvider, useLocale } from "@/lib/i18n/locale";
import { SessionProvider } from "@/lib/session/session-provider";
import { MockGate } from "@/mocks/mock-gate";

function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Reads are idempotent: retry transient network failures a little, never 4xx.
        retry: (count, error) =>
          count < 2 && error instanceof ApiError && ["NETWORK_ERROR", "TIMEOUT"].includes(error.code),
        refetchOnWindowFocus: false,
        staleTime: 30_000,
      },
      mutations: { retry: false },
    },
  });
}

function Directional({ children }: { children: React.ReactNode }) {
  const { dir } = useLocale();
  return (
    <DirectionProvider dir={dir}>
      <TooltipProvider>{children}</TooltipProvider>
    </DirectionProvider>
  );
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(makeQueryClient);
  return (
    <MockGate>
      <QueryClientProvider client={queryClient}>
        <LocaleProvider>
          <Directional>
            <SessionProvider>{children}</SessionProvider>
          </Directional>
        </LocaleProvider>
      </QueryClientProvider>
    </MockGate>
  );
}
