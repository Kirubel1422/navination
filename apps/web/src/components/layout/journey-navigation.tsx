"use client";

import { Check } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useLocale } from "@/lib/i18n/locale";
import { cn } from "@/lib/utils";

/** The three-stop workflow as a small route: done stops are linked, the current one is saffron. */
export function JourneyNavigation() {
  const pathname = usePathname();
  const { t } = useLocale();
  if (pathname.startsWith("/data")) return null; // the open-data page is not part of the route
  const current = pathname.startsWith("/journeys/") ? 2 : pathname === "/" ? 0 : 1;
  const steps = [t("workflowDiscover"), t("workflowChoose"), t("workflowPlan")];
  return (
    <nav aria-label={t("workflowLabel")}>
      <ol className="route-bar mx-auto flex max-w-xl items-center">
        {steps.map((label, index) => {
          const state = index < current ? "done" : index === current ? "current" : "upcoming";
          return (
            <li
              key={label}
              data-state={state}
              aria-current={state === "current" ? "step" : undefined}
              className={cn("flex min-w-0 items-center", index > 0 && "flex-1")}
            >
              <span className="flex min-w-0 items-center gap-2 text-[0.8rem]">
                <span
                  aria-hidden="true"
                  className={cn(
                    "grid size-5 shrink-0 place-items-center rounded-full text-[0.68rem] font-semibold",
                    state === "done" && "bg-gulf text-white",
                    state === "current" && "bg-saffron text-ink ring-4 ring-[#fbe3b8]",
                    state === "upcoming" && "border-2 border-ghaf text-muted-foreground",
                  )}
                >
                  {state === "done" ? <Check className="size-3" strokeWidth={3} /> : index + 1}
                </span>
                {state === "done" ? (
                  <Link href={index === 0 ? "/" : "/discover"} className="truncate rounded text-muted-foreground hover:text-foreground hover:underline max-sm:sr-only">
                    {label}
                  </Link>
                ) : (
                  <span className={cn("truncate", state === "current" ? "font-semibold" : "text-muted-foreground max-sm:sr-only")}>{label}</span>
                )}
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
