"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, CircleAlert, Loader2, MessageSquare, RotateCcw, SendHorizontal } from "lucide-react";
import { useState } from "react";

import { AgentActivity } from "@/components/layout/agent-activity";
import { useAnnounce } from "@/components/layout/announcer";
import { ErrorState, errorMessageKey } from "@/components/layout/states";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { AiChip, StatusChip } from "@/features/services/badges";
import { api } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/query-keys";
import type { CoachMessage, CoachTurn, Journey, MessageList, SuggestedAction } from "@/lib/api/types";
import { useLocale } from "@/lib/i18n/locale";
import { useReadySession } from "@/lib/session/session-provider";

interface PendingMessage {
  clientMessageId: string;
  message: string;
  stepId: string | null;
}

type TurnMeta = Pick<CoachTurn, "mode" | "grounding_status" | "suggested_actions" | "notices" | "agent_steps">;

function newMessageId(): string {
  return crypto.randomUUID();
}

export function CoachPanel({
  journey,
  stepId,
  onViewStep,
  onHandoff,
}: {
  journey: Journey;
  stepId: string | null;
  onViewStep: (stepId: string) => void;
  onHandoff: (stepId: string, kind: "official" | "support") => void;
}) {
  const { t } = useLocale();
  const announce = useAnnounce();
  const { token, session } = useReadySession();
  const queryClient = useQueryClient();
  const key = queryKeys.messages(session.id, session.locale, journey.id);
  const [draft, setDraft] = useState("");
  const [failed, setFailed] = useState<PendingMessage | null>(null);
  const [meta, setMeta] = useState<Record<string, TurnMeta>>({});
  const step = journey.steps.find((s) => s.id === stepId) ?? null;

  const messages = useQuery({
    queryKey: key,
    queryFn: ({ signal }) => api.listMessages({ token, signal }, journey.id),
  });

  const send = useMutation({
    mutationFn: (pending: PendingMessage) =>
      api.coach({ token }, journey.id, {
        client_message_id: pending.clientMessageId,
        message: pending.message,
        step_id: pending.stepId,
      }),
    onSuccess: (turn) => {
      queryClient.setQueryData<MessageList>(key, (current) => {
        const items = current?.items ?? [];
        const known = new Set(items.map((m) => m.id));
        const added = [turn.user_message, turn.assistant_message].filter((m) => !known.has(m.id));
        return { items: [...items, ...added] };
      });
      setMeta((current) => ({ ...current, [turn.assistant_message.id]: turn }));
      setFailed(null);
      setDraft("");
      announce(turn.assistant_message.content.slice(0, 200));
    },
    onError: (_error, pending) => setFailed(pending),
  });

  const submit = (text: string) => {
    const message = text.trim();
    if (!message || message.length > 4000) return;
    send.mutate({ clientMessageId: newMessageId(), message, stepId });
  };

  const act = (action: SuggestedAction) => {
    if (!action.step_id) return;
    if (action.type === "view_step") onViewStep(action.step_id);
    else onHandoff(action.step_id, action.type === "open_official" ? "official" : "support");
  };

  const locked = journey.is_stale;
  return (
    <section aria-labelledby="coach-heading" data-testid="coach-panel" className="surface overflow-hidden">
      <header className="space-y-1 border-b px-5 pt-5 pb-4">
        <h2 id="coach-heading" className="t-head flex items-center gap-2.5">
          <span className="grid size-8 place-items-center rounded-full bg-gulf text-white">
            <MessageSquare aria-hidden="true" className="size-4" />
          </span>
          {t("coachHeading")}
        </h2>
        <p className="text-sm text-muted-foreground">{t("coachIntro")}</p>
        <p className="flex w-fit max-w-full min-w-0 items-center gap-1.5 rounded-full bg-secondary px-3 py-1 text-xs font-medium" data-testid="coach-context">
          <span aria-hidden="true" className="size-1.5 shrink-0 rounded-full bg-saffron" />
          <span className="truncate">{step ? t("coachAboutStep", { title: step.service_card.service.title }) : t("coachGeneral")}</span>
        </p>
      </header>

      <div className="space-y-4 p-4">
        {messages.isPending ? (
          <p role="status" className="text-sm text-muted-foreground">{t("loading")}</p>
        ) : messages.error ? (
          <ErrorState error={messages.error} onRetry={() => messages.refetch()} />
        ) : (
          <ol className="max-h-[26rem] space-y-3 overflow-y-auto" aria-label={t("coachHeading")} data-testid="coach-messages">
            {messages.data.items.length === 0 && !send.isPending && (
              <li className="py-2 text-center text-sm text-muted-foreground">{t("coachEmpty")}</li>
            )}
            {messages.data.items.map((message) => (
              <MessageItem key={message.id} message={message} meta={meta[message.id]} onAction={act} locked={locked} />
            ))}
            {send.isPending && (
              <li className="me-8 flex items-center gap-3 rounded-2xl rounded-ss-sm bg-muted px-3 py-2.5 text-sm text-muted-foreground">
                <span className="typing-stops flex items-center gap-1" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </span>
                <span role="status">{t("coachSending")}</span>
              </li>
            )}
          </ol>
        )}

        {failed && !send.isPending && (
          <div role="alert" className="space-y-2 rounded-xl bg-destructive/8 p-3 text-sm" data-testid="coach-failed">
            <p>
              {t("coachFailed")} {send.error ? t(errorMessageKey(send.error)) : null}
            </p>
            <Button size="sm" variant="outline" className="rounded-full" onClick={() => send.mutate(failed)} disabled={locked}>
              <RotateCcw aria-hidden="true" />
              {t("coachRetry")}
            </Button>
          </div>
        )}

        {locked ? (
          <p className="rounded-xl bg-muted p-3 text-sm text-muted-foreground">{t("coachStaleDisabled")}</p>
        ) : (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              submit(draft);
            }}
            className="space-y-2.5"
          >
            <div className="flex flex-wrap gap-1.5">
              {(["coachSample1", "coachSample2", "coachSample3"] as const).map((sample) => (
                <button
                  key={sample}
                  type="button"
                  disabled={send.isPending}
                  onClick={() => submit(t(sample))}
                  className="rounded-full border px-3 py-1 text-xs transition-colors hover:border-gulf hover:bg-secondary disabled:opacity-50"
                >
                  {t(sample)}
                </button>
              ))}
            </div>
            <Label htmlFor={`coach-input-${journey.id}`} className="sr-only">
              {t("coachInputLabel")}
            </Label>
            <div className="rounded-2xl border bg-card transition-shadow focus-within:border-gulf focus-within:shadow-[0_0_0_3px_rgb(14_97_112/0.12)]">
              <textarea
                id={`coach-input-${journey.id}`}
                value={draft}
                maxLength={4000}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    submit(draft);
                  }
                }}
                placeholder={t("coachPlaceholder")}
                rows={2}
                disabled={send.isPending}
                className="block w-full resize-none bg-transparent px-3.5 pt-3 text-sm leading-6 outline-none focus-visible:outline-none"
              />
              <div className="flex justify-end p-2">
                <Button type="submit" size="sm" className="h-9 rounded-full px-4" disabled={send.isPending || !draft.trim()} data-testid="coach-send">
                  {send.isPending ? <Loader2 aria-hidden="true" className="animate-spin motion-reduce:animate-none" /> : <SendHorizontal aria-hidden="true" className="rtl:-scale-x-100" />}
                  {send.isPending ? t("coachSending") : t("coachSend")}
                </Button>
              </div>
            </div>
            <p className="text-[0.72rem] leading-5 text-muted-foreground">{t("coachLimits")}</p>
          </form>
        )}
      </div>
    </section>
  );
}

function MessageItem({
  message,
  meta,
  onAction,
  locked,
}: {
  message: CoachMessage;
  meta?: TurnMeta;
  onAction: (action: SuggestedAction) => void;
  locked: boolean;
}) {
  const { t } = useLocale();
  const isUser = message.role === "user";
  return (
    <li
      className={isUser ? "ms-8 rounded-2xl rounded-se-sm bg-gulf p-3 text-white" : "me-4 rounded-2xl rounded-ss-sm bg-muted p-3"}
      data-testid={`coach-message-${message.role}`}
    >
      <p className={isUser ? "sr-only" : "mb-1 text-xs font-semibold text-muted-foreground"}>{isUser ? t("coachYou") : t("coachAssistant")}</p>
      <p className="whitespace-pre-line text-sm">{message.content}</p>
      {meta && (
        <div className="mt-2 flex flex-wrap gap-1">
          <AiChip data-testid="coach-mode">{t("coachModeAi")}</AiChip>
          {meta.grounding_status === "insufficient_evidence" && (
            <StatusChip tone="saffron" icon={CircleAlert}>
              {t("coachInsufficient")}
            </StatusChip>
          )}
        </div>
      )}
      {meta && <AgentActivity steps={meta.agent_steps} />}
      {meta && meta.notices.length > 0 && (
        <ul className="mt-1 text-xs text-muted-foreground">
          {meta.notices.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
      {message.citations.length > 0 && (
        <div className="mt-2">
          <p className="flex items-center gap-1 text-xs font-medium">
            <BookOpen aria-hidden="true" className="size-3.5" />
            {t("coachCitations")}
          </p>
          <ul className="list-disc ps-5 text-xs" data-testid="coach-citations">
            {message.citations.map((source) => (
              <li key={source.id}>
                {source.url ? (
                  <a href={source.url} target="_blank" rel="noopener noreferrer" className="text-gulf underline underline-offset-2">
                    {source.title} {t("opensInNewTab")}
                  </a>
                ) : (
                  source.title
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      {meta && meta.suggested_actions.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2" aria-label={t("coachSuggested")}>
          {meta.suggested_actions.map((action, index) => (
            <Button
              key={index}
              size="sm"
              variant="outline"
              className="h-8 rounded-full bg-card"
              disabled={locked && action.type !== "view_step"}
              onClick={() => onAction(action)}
              data-testid={`coach-action-${action.type}`}
            >
              {t(`action_${action.type}`)}
            </Button>
          ))}
        </div>
      )}
    </li>
  );
}
