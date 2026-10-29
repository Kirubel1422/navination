"use client";

import { useMutation } from "@tanstack/react-query";

import { api } from "@/lib/api/endpoints";
import type { DiscoverRequest } from "@/lib/api/types";
import { useLocale } from "@/lib/i18n/locale";
import { useReadySession } from "@/lib/session/session-provider";
import { defaultSelection, loadDiscovery, saveDiscovery, savePreviousDiscovery } from "./discovery-store";

export function useDiscover() {
  const { token, session } = useReadySession();
  const { locale } = useLocale();
  return useMutation({
    mutationFn: (body: DiscoverRequest) => api.discover({ token }, body),
    onSuccess: (discovery) => {
      const previous = loadDiscovery(session.id);
      savePreviousDiscovery(previous?.discovery.status === "ready" ? previous : null);
      saveDiscovery({ sessionId: session.id, locale, discovery, selected: defaultSelection(discovery) });
    },
  });
}
