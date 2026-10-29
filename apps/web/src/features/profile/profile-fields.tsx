"use client";

import { Baby, Check, GraduationCap, IdCard, MapPin } from "lucide-react";
import { useId } from "react";
import { type Control, Controller } from "react-hook-form";

import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import type { MessageKey } from "@/lib/i18n/dictionaries";
import { useLocale } from "@/lib/i18n/locale";
import { cn } from "@/lib/utils";
import { EMIRATES, LIFE_STAGES, RESIDENCY, UNKNOWN, type ProfileFormValues } from "./profile-schema";

type Icon = typeof MapPin;

function Question({
  id,
  icon: Icon,
  label,
  why,
  answered,
  children,
}: {
  id: string;
  icon: Icon;
  label: string;
  why: string;
  answered: boolean;
  children: React.ReactNode;
}) {
  return (
    <fieldset className="surface space-y-3 p-4" aria-describedby={`${id}-why`}>
      <legend className="float-start mb-1 flex w-full items-start gap-3">
        <span
          aria-hidden="true"
          className={cn(
            "grid size-9 shrink-0 place-items-center rounded-full transition-colors",
            answered ? "bg-gulf text-white" : "bg-secondary text-gulf",
          )}
        >
          {answered ? <Check className="size-4" strokeWidth={3} /> : <Icon className="size-4" />}
        </span>
        <span className="min-w-0">
          <span className="block font-semibold leading-snug">{label}</span>
          <span id={`${id}-why`} className="mt-0.5 block text-xs leading-5 text-muted-foreground">
            {why}
          </span>
        </span>
      </legend>
      {children}
    </fieldset>
  );
}

/** Answer tiles: real radios, so keyboard and screen readers work as usual. */
function Tiles({
  name,
  value,
  onChange,
  options,
  columns = 2,
}: {
  name: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  columns?: 1 | 2;
}) {
  const base = useId();
  return (
    <RadioGroup value={value} onValueChange={onChange} name={name} className={cn("clear-both grid gap-2", columns === 2 && "grid-cols-2")}>
      {options.map((option) => {
        const unknown = option.value === UNKNOWN;
        return (
          <label
            key={option.value}
            htmlFor={`${base}-${option.value}`}
            className={cn(
              "flex min-h-11 cursor-pointer items-center gap-2.5 rounded-xl border px-3 py-2 text-sm transition-colors hover:border-gulf",
              "has-[[data-state=checked]]:border-gulf has-[[data-state=checked]]:bg-secondary has-[[data-state=checked]]:font-semibold",
              unknown ? "border-dashed bg-transparent text-muted-foreground" : "bg-card",
              unknown && columns === 2 && "col-span-2",
            )}
          >
            <RadioGroupItem value={option.value} id={`${base}-${option.value}`} />
            <span>{option.label}</span>
          </label>
        );
      })}
    </RadioGroup>
  );
}


/** The four optional profile questions as answer tiles (shared by the profile sheet and the
 * "make your plan fit you" dialog). */
export function ProfileFields({ control, values }: { control: Control<ProfileFormValues>; values: ProfileFormValues }) {
  const { t } = useLocale();
  const notSure = { value: UNKNOWN, label: t("notSure") };
  return (
    <>
      <Question id="emirate" icon={MapPin} label={t("field_emirate")} why={t("why_emirate")} answered={values.emirate !== UNKNOWN}>
        <Controller
          control={control}
          name="emirate"
          render={({ field }) => (
            <Tiles
              name="emirate"
              value={field.value}
              onChange={field.onChange}
              options={[...EMIRATES.map((e) => ({ value: e, label: t(`emirate_${e}` as MessageKey) })), notSure]}
            />
          )}
        />
      </Question>
      <Question
        id="residency"
        icon={IdCard}
        label={t("field_residency_status")}
        why={t("why_residency_status")}
        answered={values.residency_status !== UNKNOWN}
      >
        <Controller
          control={control}
          name="residency_status"
          render={({ field }) => (
            <Tiles
              name="residency_status"
              value={field.value}
              onChange={field.onChange}
              options={[...RESIDENCY.map((r) => ({ value: r, label: t(`residency_${r}` as MessageKey) })), notSure]}
            />
          )}
        />
      </Question>
      <Question
        id="stage"
        icon={Baby}
        label={t("field_life_stage")}
        why={t("why_life_stage")}
        answered={values.life_stage !== UNKNOWN}
      >
        <Controller
          control={control}
          name="life_stage"
          render={({ field }) => (
            <Tiles
              name="life_stage"
              value={field.value}
              onChange={field.onChange}
              options={[...LIFE_STAGES.map((st) => ({ value: st, label: t(`stage_${st}` as MessageKey) })), notSure]}
            />
          )}
        />
      </Question>
      <Question
        id="degree"
        icon={GraduationCap}
        label={t("field_degree_issued_outside_uae")}
        why={t("why_degree_issued_outside_uae")}
        answered={values.degree_issued_outside_uae !== UNKNOWN}
      >
        <Controller
          control={control}
          name="degree_issued_outside_uae"
          render={({ field }) => (
            <Tiles
              name="degree_issued_outside_uae"
              value={field.value}
              columns={1}
              onChange={field.onChange}
              options={[
                { value: "true", label: t("degree_true") },
                { value: "false", label: t("degree_false") },
                notSure,
              ]}
            />
          )}
        />
      </Question>
    </>
  );
}
