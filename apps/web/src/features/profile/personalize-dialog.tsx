"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Sparkles } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import { useForm, useWatch } from "react-hook-form";

import { LocationChip } from "@/components/layout/location-chip";
import { ErrorState } from "@/components/layout/states";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useLocale } from "@/lib/i18n/locale";
import { useSession } from "@/lib/session/session-provider";
import { readStored, writeStored } from "@/lib/session/storage";
import { ProfileFields } from "./profile-fields";
import { EMPTY_PROFILE, UNKNOWN, profileFormSchema, toFormValues, toProfileRequest, type ProfileFormValues } from "./profile-schema";
import { useUpdateProfile } from "./use-update-profile";

/**
 * Before the first search of a session, offers the optional profile: a few answers add, remove
 * and order the stages of the plan. Asked once per session, and never when every answer is given.
 */
export function usePersonalizeBeforeSearch() {
  const { state } = useSession();
  const [open, setOpen] = useState(false);
  const pending = useRef<(() => void) | null>(null);

  const guard = useCallback(
    (run: () => void) => {
      const profile = state.status === "ready" ? state.session.profile : EMPTY_PROFILE;
      const complete = Object.values(profile).every((value) => value !== null);
      if (state.status !== "ready" || complete || readStored<boolean>("personalizePrompted")) {
        run();
        return;
      }
      pending.current = run;
      setOpen(true);
    },
    [state],
  );

  const finish = useCallback(() => {
    writeStored("personalizePrompted", true);
    setOpen(false);
    const run = pending.current;
    pending.current = null;
    run?.();
  }, []);

  const dialog = <PersonalizeDialog open={open} onClose={() => setOpen(false)} onDone={finish} />;
  return { guard, dialog };
}

function PersonalizeDialog({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const { t } = useLocale();
  const { state } = useSession();
  const mutation = useUpdateProfile();
  const current = state.status === "ready" ? state.session.profile : EMPTY_PROFILE;
  const form = useForm<ProfileFormValues>({ resolver: zodResolver(profileFormSchema), values: toFormValues(current) });
  const values = useWatch({ control: form.control }) as ProfileFormValues;
  const answered = Object.values(values).filter((v) => v !== UNKNOWN).length;

  const apply = form.handleSubmit(async (next) => {
    await mutation.mutateAsync(toProfileRequest(next));
    onDone();
  });

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="max-h-[92dvh] gap-0 overflow-hidden rounded-[1.75rem] bg-salt p-0 sm:max-w-2xl" data-testid="personalize-dialog">
        <form onSubmit={apply} className="flex max-h-[92dvh] min-h-0 flex-col" noValidate>
          <div className="min-h-0 flex-1 overflow-y-auto">
            <div className="relative h-24 overflow-hidden" aria-hidden="true">
              {/* eslint-disable-next-line @next/next/no-img-element -- pixel-art asset */}
              <img src="/art/dunes.png" alt="" className="pixel art-flip absolute inset-0 h-full w-full object-cover object-[80%_75%]" />
              <div className="absolute inset-x-0 bottom-0 h-10 bg-gradient-to-b from-transparent to-salt" />
            </div>
            <DialogHeader className="space-y-2 px-6 pb-4 text-start">
              <span className="inline-flex w-fit items-center gap-1.5 rounded-full bg-[#efeaf7] px-2.5 py-1 text-xs font-semibold text-[#4b357c]">
                <Sparkles aria-hidden="true" className="size-3.5" />
                {t("tailoredHeading")}
              </span>
              <DialogTitle className="t-title">{t("personalizeTitle")}</DialogTitle>
              <DialogDescription className="max-w-[56ch] text-[0.95rem]">{t("personalizeLede")}</DialogDescription>
              <p className="max-w-[60ch] rounded-2xl bg-card px-4 py-3 text-sm ring-1 ring-border">{t("personalizeExample")}</p>
            </DialogHeader>
            <div className="space-y-3 px-6 pb-6">
              <ProfileFields control={form.control} values={values} />
              <div className="surface flex flex-wrap items-center justify-between gap-3 p-4">
                <p className="text-sm text-muted-foreground">{t("locationPrivacy")}</p>
                <LocationChip />
              </div>
              {mutation.error ? <ErrorState error={mutation.error} /> : null}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 border-t bg-card px-6 py-3">
            <Button type="submit" className="h-11 rounded-full px-5" disabled={mutation.isPending || answered === 0} data-testid="personalize-apply">
              <Sparkles aria-hidden="true" />
              {mutation.isPending ? t("personalizeSaving") : t("personalizeApply")}
            </Button>
            <Button type="button" variant="ghost" className="h-11 rounded-full px-4" onClick={onDone} data-testid="personalize-skip">
              {t("personalizeSkip")}
            </Button>
            <span className="ms-auto text-xs font-medium text-muted-foreground" aria-live="polite">
              {t("personalizeAnswered", { n: answered })}
            </span>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
