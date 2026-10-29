"use client";

import { Baby, BookOpen, Database, GraduationCap, LockKeyhole, Route } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { AgentLoader } from "@/components/layout/agent-loader";
import { ErrorState } from "@/components/layout/states";
import { Button } from "@/components/ui/button";
import { useLocale } from "@/lib/i18n/locale";
import { useStored } from "@/lib/session/storage";
import { DiscoveryForm, SUPPORTED_EXAMPLES } from "./discovery-form";
import { useDiscover } from "./use-discover";

export function HomeView() {
  const { t, locale } = useLocale();
  const router = useRouter();
  const discover = useDiscover();
  const activeJourney = useStored<string>("activeJourney");
  const run = (query: string) => discover.mutate({ query, clarification_answer: null }, { onSuccess: () => router.push("/discover") });
  const examples = locale === "ar"
    ? [{ icon: GraduationCap, title: t("exampleDegree") }, { icon: Baby, title: t("exampleBaby") }]
    : [{ icon: GraduationCap, title: t("exampleDegree") }, { icon: BookOpen, title: t("exampleSchool") }, { icon: Baby, title: t("exampleBaby") }];

  return (
    <div className="space-y-10">
      {activeJourney && (
        <section data-testid="resume-card" className="surface flex flex-wrap items-center justify-between gap-4 rounded-2xl p-4 ps-5">
          <div className="flex items-center gap-3">
            <span className="grid size-10 place-items-center rounded-full bg-accent text-saffron-ink"><Route className="size-5" aria-hidden="true" /></span>
            <div>
              <h2 className="font-semibold">{t("resumeHeading")}</h2>
              <p className="text-sm text-muted-foreground">{t("resumeBody")}</p>
            </div>
          </div>
          <Button asChild className="h-10 rounded-full px-5"><Link href={`/journeys/${encodeURIComponent(activeJourney)}`}>{t("resumeAction")}</Link></Button>
        </section>
      )}

      <section aria-labelledby="home-heading" className="grid grid-cols-1 items-end gap-x-10 gap-y-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.9fr)]">
        <div className="space-y-4 lg:pb-6">
          <h1 id="home-heading" className="t-display max-w-[13ch]">{t("homeHeading")}</h1>
          <p className="max-w-md text-lg text-muted-foreground">{t("homeLede")}</p>
        </div>
        {/* eslint-disable-next-line @next/next/no-img-element -- pixel-art asset scaled with nearest-neighbour */}
        <img
          src="/art/dunes.png"
          alt=""
          aria-hidden="true"
          className="pixel art-flip pointer-events-none order-first h-36 w-full object-cover object-[70%_bottom] sm:h-48 lg:order-none lg:-me-16 lg:h-80 lg:w-[calc(100%+4rem)] lg:object-contain lg:object-[100%_100%]"
        />
        <div className="lg:col-span-2 lg:max-w-2xl">
          <DiscoveryForm pending={discover.isPending} onSubmit={run} />
          {discover.isPending && <p role="status" className="sr-only" data-testid="agent-working">{t("agentWorking")}</p>}
          {discover.error ? <div className="mt-4"><ErrorState error={discover.error} onRetry={() => discover.reset()} /></div> : null}
        </div>
      </section>

      <section aria-labelledby="examples-heading" className="max-w-2xl space-y-3">
        <h2 id="examples-heading" className="t-label">{t("examplesHeading")}</h2>
        <ul className="flex flex-wrap gap-2">
          {SUPPORTED_EXAMPLES[locale].map((example, index) => {
            const { icon: Icon, title } = examples[index];
            return (
              <li key={example}>
                <button
                  type="button"
                  disabled={discover.isPending}
                  onClick={() => run(example)}
                  title={example}
                  className="inline-flex h-11 items-center gap-2 rounded-full border bg-card ps-1.5 pe-4 text-[0.95rem] transition-colors hover:border-gulf hover:bg-secondary disabled:cursor-wait disabled:opacity-60"
                >
                  <span className="grid size-8 place-items-center rounded-full bg-secondary text-gulf"><Icon aria-hidden="true" className="size-4" strokeWidth={1.8} /></span>
                  {title}
                  <span className="sr-only">: {example}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </section>

      <ul className="flex max-w-2xl flex-wrap gap-x-6 gap-y-2 border-t pt-5 text-sm text-muted-foreground">
        <li className="flex items-center gap-2"><LockKeyhole aria-hidden="true" className="size-4 text-gulf" />{t("guestNote")}</li>
        <li className="flex items-center gap-2"><Database aria-hidden="true" className="size-4 text-gulf" />{t("trustSources")}</li>
      </ul>

      <AgentLoader open={discover.isPending} runId={discover.submittedAt} task="search" />
    </div>
  );
}
