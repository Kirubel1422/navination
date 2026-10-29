import { describe, expect, it } from "vitest";

import { profileFormSchema, toFormValues, toProfileRequest } from "./profile-schema";

describe("profile form mapping", () => {
  it("keeps unknown distinct from a negative answer", () => {
    const unknown = toProfileRequest(
      profileFormSchema.parse({
        emirate: "unknown",
        residency_status: "unknown",
        life_stage: "unknown",
        degree_issued_outside_uae: "unknown",
      }),
    );
    expect(unknown.degree_issued_outside_uae).toBeNull();
    const negative = toProfileRequest(
      profileFormSchema.parse({ ...toFormValues(unknown), degree_issued_outside_uae: "false" }),
    );
    expect(negative.degree_issued_outside_uae).toBe(false);
  });

  it("round-trips every field", () => {
    const profile = {
      emirate: "dubai",
      residency_status: "resident",
      life_stage: "parent",
      degree_issued_outside_uae: true,
    } as const;
    expect(toProfileRequest(toFormValues(profile))).toEqual(profile);
  });

  it("rejects values outside the contract", () => {
    expect(() =>
      profileFormSchema.parse({
        emirate: "atlantis",
        residency_status: "unknown",
        life_stage: "unknown",
        degree_issued_outside_uae: "unknown",
      }),
    ).toThrow();
  });
});
