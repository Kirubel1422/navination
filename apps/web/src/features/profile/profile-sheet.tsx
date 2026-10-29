"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { UserRound } from "lucide-react";
import { useEffect, useId, useState } from "react";
import { Controller, useForm } from "react-hook-form";

import { useAnnounce } from "@/components/layout/announcer";
import { ErrorState } from "@/components/layout/states";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
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
import { useSession } from "@/lib/session/session-provider";
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

function FieldShell({
  id,
  label,
  why,
  children,
}: {
  id: string;
  label: string;
  why: string;
  children: React.ReactNode;
}) {
  return (
    <fieldset className="space-y-2 rounded-lg border p-3" aria-describedby={`${id}-why`}>
      <legend className="px-1 text-sm font-medium">{label}</legend>
      <p id={`${id}-why`} className="text-xs text-muted-foreground">
        {why}
      </p>
      {children}
    </fieldset>
  );
}

function Radios({
  name,
  value,
  onChange,
  options,
}: {
  name: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
}) {
  const base = useId();
  return (
    <RadioGroup value={value} onValueChange={onChange} name={name} className="gap-2">
      {options.map((option) => (
        <div key={option.value} className="flex items-center gap-2">
          <RadioGroupItem value={option.value} id={`${base}-${option.value}`} />
          <Label htmlFor={`${base}-${option.value}`} className="font-normal">
            {option.label}
          </Label>
        </div>
      ))}
    </RadioGroup>
  );
}

export function ProfileSheet() {
  const { t, dir } = useLocale();
  const { state } = useSession();
  const announce = useAnnounce();
  const [open, setOpen] = useState(false);
  const mutation = useUpdateProfile();
  const emirateId = useId();
  const current = state.status === "ready" ? state.session.profile : EMPTY_PROFILE;

  const form = useForm<ProfileFormValues>({
    resolver: zodResolver(profileFormSchema),
    values: toFormValues(current),
  });

  useEffect(() => onOpenProfileSheet(() => setOpen(true)), []);

  if (state.status !== "ready") return null;

  const save = async (values: ProfileFormValues) => {
    const profile = toProfileRequest(values);
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
      <SheetContent side={dir === "rtl" ? "left" : "right"} className="w-full overflow-y-auto sm:max-w-md">
        <form onSubmit={form.handleSubmit(save)} className="flex h-full flex-col" noValidate>
          <SheetHeader>
            <SheetTitle>{t("profileTitle")}</SheetTitle>
            <SheetDescription>{t("profileIntro")}</SheetDescription>
          </SheetHeader>
          <div className="flex-1 space-y-4 px-4">
            <FieldShell id="emirate" label={t("field_emirate")} why={t("why_emirate")}>
              <Controller
                control={form.control}
                name="emirate"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange} dir={dir}>
                    <SelectTrigger id={emirateId} aria-label={t("field_emirate")} className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={UNKNOWN}>{t("notSure")}</SelectItem>
                      {EMIRATES.map((e) => (
                        <SelectItem key={e} value={e}>
                          {t(`emirate_${e}` as MessageKey)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </FieldShell>
            <FieldShell id="residency" label={t("field_residency_status")} why={t("why_residency_status")}>
              <Controller
                control={form.control}
                name="residency_status"
                render={({ field }) => (
                  <Radios
                    name="residency_status"
                    value={field.value}
                    onChange={field.onChange}
                    options={[
                      notSure,
                      ...RESIDENCY.map((r) => ({ value: r, label: t(`residency_${r}` as MessageKey) })),
                    ]}
                  />
                )}
              />
            </FieldShell>
            <FieldShell id="stage" label={t("field_life_stage")} why={t("why_life_stage")}>
              <Controller
                control={form.control}
                name="life_stage"
                render={({ field }) => (
                  <Radios
                    name="life_stage"
                    value={field.value}
                    onChange={field.onChange}
                    options={[notSure, ...LIFE_STAGES.map((s) => ({ value: s, label: t(`stage_${s}` as MessageKey) }))]}
                  />
                )}
              />
            </FieldShell>
            <FieldShell
              id="degree"
              label={t("field_degree_issued_outside_uae")}
              why={t("why_degree_issued_outside_uae")}
            >
              <Controller
                control={form.control}
                name="degree_issued_outside_uae"
                render={({ field }) => (
                  <Radios
                    name="degree_issued_outside_uae"
                    value={field.value}
                    onChange={field.onChange}
                    options={[
                      notSure,
                      { value: "true", label: t("degree_true") },
                      { value: "false", label: t("degree_false") },
                    ]}
                  />
                )}
              />
            </FieldShell>
            <Alert>
              <AlertDescription>{t("profileStaleNote")}</AlertDescription>
            </Alert>
            {mutation.error ? <ErrorState error={mutation.error} /> : null}
          </div>
          <SheetFooter className="flex-row flex-wrap gap-2">
            <Button type="submit" disabled={mutation.isPending} data-testid="profile-save">
              {mutation.isPending ? t("profileSaving") : t("profileSave")}
            </Button>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              {t("profileSkip")}
            </Button>
            <Button
              type="button"
              variant="ghost"
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
