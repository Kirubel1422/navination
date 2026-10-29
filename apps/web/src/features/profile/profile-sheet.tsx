"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Baby, Check, GraduationCap, IdCard, LockKeyhole, MapPin, Navigation, UserRound } from "lucide-react";
import { useEffect, useId, useState } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";

import { useAnnounce } from "@/components/layout/announcer";
import { LocationChip } from "@/components/layout/location-chip";
import { ErrorState } from "@/components/layout/states";
import { Button } from "@/components/ui/button";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import type { MessageKey } from "@/lib/i18n/dictionaries";
import { useLocale } from "@/lib/i18n/locale";
import { useSharedLocation } from "@/lib/location";
import { useSession } from "@/lib/session/session-provider";
import { cn } from "@/lib/utils";
import { onOpenProfileSheet } from "./profile-events";
import {
  EMIRATES,
  EMPTY_PROFILE,
  LIFE_STAGES,
  RESIDENCY,
  UNKNOWN,
  profileFormSchema,
  toFormValues,
  toProfileRequest,
  type ProfileFormValues,
} from "./profile-schema";
import { useUpdateProfile } from "./use-update-profile";

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

export function ProfileSheet() {
  const { t, dir } = useLocale();
  const { state } = useSession();
  const announce = useAnnounce();
  const [open, setOpen] = useState(false);
  const mutation = useUpdateProfile();
  const { location } = useSharedLocation();
  const current = state.status === "ready" ? state.session.profile : EMPTY_PROFILE;

  const form = useForm<ProfileFormValues>({
    resolver: zodResolver(profileFormSchema),
    values: toFormValues(current),
  });
  const values = useWatch({ control: form.control }) as ProfileFormValues;
  const answered = Object.values(values).filter((v) => v !== UNKNOWN).length;

  useEffect(() => onOpenProfileSheet(() => setOpen(true)), []);

  if (state.status !== "ready") return null;

  const save = async (next: ProfileFormValues) => {
    const profile = toProfileRequest(next);
    const before = state.session.context_revision;
    const session = await mutation.mutateAsync(profile);
    announce(session.context_revision === before ? t("profileUnchanged") : t("profileSaved"));
    setOpen(false);
  };

  const notSure = { value: UNKNOWN, label: t("notSure") };
  return (
    <Sheet open={open} onOpenChange={(next) => (setOpen(next), mutation.reset())}>
      <SheetTrigger asChild>
        <Button variant="outline" size="sm" className="h-9 rounded-full bg-card px-3" data-testid="profile-open">
          <UserRound aria-hidden="true" />
          <span className="max-sm:sr-only">{t("profileButton")}</span>
        </Button>
      </SheetTrigger>
      <SheetContent side={dir === "rtl" ? "left" : "right"} className="gap-0 overflow-hidden bg-salt p-0 data-[side=left]:w-full data-[side=right]:w-full data-[side=left]:sm:max-w-lg data-[side=right]:sm:max-w-lg">
        <form onSubmit={form.handleSubmit(save)} className="flex h-full min-h-0 flex-col" noValidate>
          <div className="min-h-0 flex-1 overflow-y-auto">
            <div className="relative h-28 overflow-hidden" aria-hidden="true">
              {/* eslint-disable-next-line @next/next/no-img-element -- pixel-art asset */}
              <img src="/art/dunes.png" alt="" className="pixel art-flip absolute inset-0 h-full w-full object-cover object-[80%_75%]" />
              <div className="absolute inset-x-0 bottom-0 h-10 bg-gradient-to-b from-transparent to-salt" />
            </div>
            <SheetHeader className="space-y-2 px-5 pt-1 pb-4">
              <p className="t-label">{t("profileTitle")}</p>
              <SheetTitle className="t-title">{t("profileHello")}</SheetTitle>
              <SheetDescription>{t("profileLede")}</SheetDescription>
              <div className="space-y-1.5 pt-1">
                <div className="progress-tiles" aria-hidden="true">
                  {[0, 1, 2, 3].map((i) => (
                    <span key={i} data-state={i < answered ? "done" : "todo"} />
                  ))}
                </div>
                <p className="text-xs font-medium text-muted-foreground" aria-live="polite">
                  {t("profileAnswered", { n: answered })}
                </p>
              </div>
            </SheetHeader>

            <div className="space-y-3 px-5 pb-6">
              <Question id="emirate" icon={MapPin} label={t("field_emirate")} why={t("why_emirate")} answered={values.emirate !== UNKNOWN}>
                <Controller
                  control={form.control}
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
                  control={form.control}
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
                  control={form.control}
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
                  control={form.control}
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

              <section aria-labelledby="profile-location" className="surface flex flex-wrap items-center justify-between gap-3 p-4">
                <div className="flex min-w-0 items-start gap-3">
                  <span
                    aria-hidden="true"
                    className={cn(
                      "grid size-9 shrink-0 place-items-center rounded-full",
                      location ? "bg-mangrove text-white" : "bg-secondary text-gulf",
                    )}
                  >
                    <Navigation className="size-4 rtl:-scale-x-100" />
                  </span>
                  <div className="min-w-0">
                    <h3 id="profile-location" className="font-semibold leading-snug">
                      {t("profileLocationHeading")}
                    </h3>
                    <p className="text-xs leading-5 text-muted-foreground">
                      {location ? t("profileLocationOn") : t("profileLocationOff")}. {t("locationPrivacy")}
                    </p>
                  </div>
                </div>
                <LocationChip />
              </section>

              <p className="flex items-start gap-2 px-1 text-xs leading-5 text-muted-foreground">
                <LockKeyhole aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
                <span>
                  {t("profilePrivacy")} {t("profileStaleNote")}
                </span>
              </p>
              {mutation.error ? <ErrorState error={mutation.error} /> : null}
            </div>
          </div>

          <SheetFooter className="flex-row flex-nowrap items-center gap-1.5 border-t bg-card px-4 py-3 sm:px-5">
            <Button type="submit" className="h-10 rounded-full px-5" disabled={mutation.isPending} data-testid="profile-save">
              {mutation.isPending ? t("profileSaving") : t("profileSave")}
            </Button>
            <Button type="button" variant="ghost" className="h-10 rounded-full px-3 max-sm:hidden" onClick={() => setOpen(false)}>
              {t("profileSkip")}
            </Button>
            <Button
              type="button"
              variant="ghost"
              className="ms-auto h-10 rounded-full px-2.5 text-muted-foreground"
              disabled={mutation.isPending}
              data-testid="profile-clear"
              onClick={() => save(toFormValues(EMPTY_PROFILE))}
            >
              {t("profileClear")}
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  );
}
