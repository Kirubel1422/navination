"use client";

import { useMutation } from "@tanstack/react-query";

import { api } from "@/lib/api/endpoints";
import type { DiscoverRequest } from "@/lib/api/types";
import { useLocale } from "@/lib/i18n/locale";
import { sharedPoint } from "@/lib/location";
import { useReadySession } from "@/lib/session/session-provider";
import { defaultSelection, loadDiscovery, saveDiscovery, savePreviousDiscovery } from "./discovery-store";

export function useDiscover() {
  const { token, session } = useReadySession();
  const { locale } = useLocale();
  return useMutation({
    // The location (if the person shared it) lets the agent look for centres near them.
    mutationFn: (body: DiscoverRequest) => api.discover({ token }, { ...body, location: body.location ?? sharedPoint() }),
    onSuccess: (discovery) => {
      const previous = loadDiscovery(session.id);
      savePreviousDiscovery(previous?.discovery.status === "ready" ? previous : null);
      saveDiscovery({ sessionId: session.id, locale, discovery, selected: defaultSelection(discovery) });
    },
  });
}
