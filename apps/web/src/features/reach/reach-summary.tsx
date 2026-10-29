"use client";

import type { Reach } from "@/lib/api/types";
import { ContactList } from "./contact-list";
import { NearbyDialog } from "./nearby-dialog";

/** On a service card or step: phone numbers to call, and the "Nearest centres" popup. */
export function ReachSummary({
  reach,
  serviceId,
  serviceTitle,
}: {
  reach: Reach | null | undefined;
  serviceId: string;
  serviceTitle: string;
}) {
  return (
    <div className="space-y-3">
      {reach && reach.contacts.length > 0 && <ContactList contacts={reach.contacts.slice(0, 2)} compact />}
      <NearbyDialog serviceId={serviceId} serviceTitle={serviceTitle} seed={reach} />
    </div>
  );
}
