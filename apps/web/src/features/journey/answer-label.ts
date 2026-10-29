import type { MessageKey } from "@/lib/i18n/dictionaries";

type T = (key: MessageKey, params?: Record<string, string | number>) => string;

const VALUE_PREFIX: Record<string, string> = {
  emirate: "emirate_",
  residency_status: "residency_",
  life_stage: "stage_",
  degree_issued_outside_uae: "degree_",
};

/** "Umm Al Quwain", "UAE resident", "Yes, issued outside the UAE" for a stored profile answer. */
export function answerLabel(t: T, field: string, value: string): string {
  const key = `${VALUE_PREFIX[field] ?? ""}${value}` as MessageKey;
  const label = t(key);
  return label === key ? value : label;
}

export function fieldLabel(t: T, field: string): string {
  return t(`field_${field}` as MessageKey);
}
