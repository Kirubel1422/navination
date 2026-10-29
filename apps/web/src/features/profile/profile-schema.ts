import { z } from "zod";

import type { ProfileRequest } from "@/lib/api/types";

export const UNKNOWN = "unknown";

export const EMIRATES = [
  "abu_dhabi",
  "dubai",
  "sharjah",
  "ajman",
  "umm_al_quwain",
  "ras_al_khaimah",
  "fujairah",
] as const;
export const RESIDENCY = ["citizen", "resident", "visitor"] as const;
export const LIFE_STAGES = ["student", "worker", "parent", "other"] as const;

/** Form values keep "unknown" distinct from a negative answer ("false"). */
export const profileFormSchema = z.object({
  emirate: z.enum([UNKNOWN, ...EMIRATES]),
  residency_status: z.enum([UNKNOWN, ...RESIDENCY]),
  life_stage: z.enum([UNKNOWN, ...LIFE_STAGES]),
  degree_issued_outside_uae: z.enum([UNKNOWN, "true", "false"]),
});

export type ProfileFormValues = z.infer<typeof profileFormSchema>;

export function toFormValues(profile: ProfileRequest): ProfileFormValues {
  return {
    emirate: profile.emirate ?? UNKNOWN,
    residency_status: profile.residency_status ?? UNKNOWN,
    life_stage: profile.life_stage ?? UNKNOWN,
    degree_issued_outside_uae:
      profile.degree_issued_outside_uae === null ? UNKNOWN : profile.degree_issued_outside_uae ? "true" : "false",
  };
}

export function toProfileRequest(values: ProfileFormValues): ProfileRequest {
  return {
    emirate: values.emirate === UNKNOWN ? null : values.emirate,
    residency_status: values.residency_status === UNKNOWN ? null : values.residency_status,
    life_stage: values.life_stage === UNKNOWN ? null : values.life_stage,
    degree_issued_outside_uae:
      values.degree_issued_outside_uae === UNKNOWN ? null : values.degree_issued_outside_uae === "true",
  };
}

export const EMPTY_PROFILE: ProfileRequest = {
  emirate: null,
  residency_status: null,
  life_stage: null,
  degree_issued_outside_uae: null,
};
