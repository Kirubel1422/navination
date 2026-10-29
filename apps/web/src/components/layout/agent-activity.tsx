"use client";

import { Bot } from "lucide-react";

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import type { components } from "@/lib/api/schema.gen";
import type { MessageKey } from "@/lib/i18n/dictionaries";
import { useLocale } from "@/lib/i18n/locale";

type AgentStep = components["schemas"]["AgentStep"];

const KNOWN = new Set([
  "read_catalog",
  "list_catalog_services",
  "get_catalog_service",
  "search_official_web",
  "fetch_official_page",
  "get_step",
  "list_glossary",
  "search_bayanat_datasets",
  "get_bayanat_dataset",
  "read_bayanat_resource",
  "search_ajman_datasets",
  "get_ajman_records",
]);

/** Shows which tools the AI agent used, as a small route of stops, so people can see where an answer came from. */
export function AgentActivity({ steps }: { steps: AgentStep[] }) {
  const { t } = useLocale();
  if (steps.length === 0) return null;
  return (
    <Accordion type="single" collapsible data-testid="agent-activity">
      <AccordionItem value="activity" className="border-none">
        <AccordionTrigger className="w-fit flex-none gap-2 py-1 text-[0.8rem] font-medium text-muted-foreground hover:text-foreground hover:no-underline">
          <span className="inline-flex items-center gap-1.5">
            <Bot aria-hidden="true" className="size-4 text-dusk" />
            {t("agentActivity", { count: steps.length })}
          </span>
        </AccordionTrigger>
        <AccordionContent>
          <ol className="relative mt-1 space-y-2 border-s-2 border-dashed border-ghaf ps-4">
            {steps.map((step, index) => (
              <li key={index} className="relative text-[0.8rem] leading-5">
                <span aria-hidden="true" className="absolute -start-[1.4rem] top-1 size-2.5 rounded-full border-2 border-card bg-gulf" />
                <span className="font-medium">{KNOWN.has(step.tool) ? t(`tool_${step.tool}` as MessageKey) : step.tool}</span>
                <span className="block break-all text-muted-foreground" dir="ltr">
                  {step.detail}
                </span>
              </li>
            ))}
          </ol>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}
