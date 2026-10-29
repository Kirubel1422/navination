"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/query-keys";
import type { HandoffRequest, Journey, StepUpdateRequest } from "@/lib/api/types";
import { useReadySession } from "@/lib/session/session-provider";

export function useJourney(journeyId: string) {
  const { token, session } = useReadySession();
  const queryClient = useQueryClient();
  const key = queryKeys.journey(session.id, session.locale, journeyId);

  const journey = useQuery({
    queryKey: key,
    queryFn: ({ signal }) => api.getJourney({ token, signal }, journeyId),
  });

  // Mutations replace the cache with the authoritative object returned by the API.
  const setJourney = (value: Journey) => queryClient.setQueryData(key, value);

  const updateStep = useMutation({
    mutationFn: ({ stepId, body }: { stepId: string; body: StepUpdateRequest }) =>
      api.updateStep({ token }, journeyId, stepId, body),
    onSuccess: setJourney,
  });

  const replan = useMutation({
    mutationFn: () => api.replan({ token }, journeyId),
    onSuccess: setJourney,
  });

  const handoff = useMutation({
    mutationFn: (body: HandoffRequest) => api.createHandoff({ token }, journeyId, body),
  });

  return { journey, updateStep, replan, handoff };
}
