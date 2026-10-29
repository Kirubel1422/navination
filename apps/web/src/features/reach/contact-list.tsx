"use client";

import { Check, Copy, Phone } from "lucide-react";
import { useState } from "react";

import type { Contact } from "@/lib/api/types";
import { useLocale } from "@/lib/i18n/locale";
import { cn } from "@/lib/utils";

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

function host(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

function ContactRow({ contact, compact }: { contact: Contact; compact?: boolean }) {
  const { t } = useLocale();
  const [copied, setCopied] = useState(false);
  return (
    <li
      className={cn("flex flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-2xl border bg-card", compact ? "px-3 py-2.5" : "px-4 py-3")}
      data-testid="contact"
    >
      <div className="min-w-0">
        <p className="text-sm font-medium">{contact.label}</p>
        <p className={cn("font-semibold tabular-nums tracking-wide", compact ? "text-base" : "text-lg")} dir="ltr">
          {contact.phone}
        </p>
        {contact.hours && <p className="text-xs text-muted-foreground">{contact.hours}</p>}
        <a
          href={contact.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-muted-foreground underline decoration-ghaf underline-offset-2 hover:text-foreground"
        >
          {t("contactFrom", { site: host(contact.source_url) })}
          <span className="sr-only"> {t("opensInNewTab")}</span>
        </a>
      </div>
      <div className="flex items-center gap-1.5">
        <a
          href={contact.tel}
          className="inline-flex h-10 items-center gap-2 rounded-full bg-mangrove px-4 text-sm font-semibold text-white hover:bg-[#256a4b]"
          data-testid="contact-call"
        >
          <Phone aria-hidden="true" className="size-4" />
          {t("callAction")}
          <span className="sr-only">
            {" "}
            {contact.label} {contact.phone}
          </span>
        </a>
        <button
          type="button"
          onClick={async () => {
            if (await copyText(contact.phone)) {
              setCopied(true);
              window.setTimeout(() => setCopied(false), 1800);
            }
          }}
          aria-label={copied ? t("copied") : `${t("copyNumber")}: ${contact.phone}`}
          title={copied ? t("copied") : t("copyNumber")}
          className="grid size-10 place-items-center rounded-full border bg-card text-muted-foreground hover:border-gulf hover:text-foreground"
        >
          {copied ? <Check aria-hidden="true" className="size-4 text-mangrove" /> : <Copy aria-hidden="true" className="size-4" />}
        </button>
      </div>
    </li>
  );
}

/** Published phone numbers with one-tap calling (tel: links work on phones and softphones). */
export function ContactList({ contacts, compact }: { contacts: Contact[]; compact?: boolean }) {
  const { t } = useLocale();
  if (contacts.length === 0) return null;
  return (
    <section aria-label={t("contactsHeading")} className="space-y-2">
      <h4 className="t-label flex items-center gap-1.5">
        <Phone aria-hidden="true" className="size-3.5" />
        {t("contactsHeading")}
      </h4>
      <ul className="space-y-2">
        {contacts.map((contact) => (
          <ContactRow key={`${contact.phone}-${contact.label}`} contact={contact} compact={compact} />
        ))}
      </ul>
    </section>
  );
}
