"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/endpoints";
import type { ProfileRequest } from "@/lib/api/types";
import { useSession } from "@/lib/session/session-provider";

export function useUpdateProfile() {
  const { state, setSession } = useSession();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (profile: ProfileRequest) => {
      if (state.status !== "ready") throw new Error("Session not ready");
      return api.replaceProfile({ token: state.token }, profile);
    },
    onSuccess: async (session) => {
      setSession(session);
      // Profile-dependent data must be re-evaluated from the backend.
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["service"] }),
        queryClient.invalidateQueries({ queryKey: ["journey"] }),
      ]);
    },
  });
}
