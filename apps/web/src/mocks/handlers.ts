/**
 * Isolated mock backend for NEXT_PUBLIC_API_MODE=mock (independent UI work and demos without the
 * API). Responses come from contract fixtures; a little in-memory state lets all five features be
 * exercised. Business rules here are deliberately minimal and never used in live mode.
 */
import { delay } from "msw";
import { HttpResponse, http } from "msw/http";

import type {
  NearbyRequest,
  CoachRequest,
  CoachTurn,
  DiscoverRequest,
  Discovery,
  Handoff,
  HandoffRequest,
  Journey,
  ProfileRequest,
  Session,
  StepUpdateRequest,
} from "@/lib/api/types";
import { API_BASE_URL } from "@/lib/config";
import * as f from "./fixtures.gen";

const clone = <T,>(value: T): T => structuredClone(value);
const now = () => new Date().toISOString();
let counter = 0;
const id = (prefix: string) => `${prefix}_mock${(counter += 1)}`;

interface MockState {
  session: Session;
  journeys: Map<string, Journey & { revision: number }>;
  messages: Map<string, CoachTurn["user_message"][]>;
  turns: Map<string, { fingerprint: string; turn: CoachTurn }>;
}

let state: MockState | null = null;
const TOKEN = "mock-token";

function requireAuth(request: Request): MockState | Response {
  if (request.headers.get("authorization") !== `Bearer ${TOKEN}` || !state) {
    return error(401, "UNAUTHORIZED", "A valid guest session is required.");
  }
  return state;
}

function error(status: number, code: string, message: string) {
  return HttpResponse.json(
    { error: { code, message, details: [], request_id: id("req") } },
    { status },
  );
}

function isResponse(value: unknown): value is Response {
  return value instanceof Response;
}

function journeyView(s: MockState, journey: Journey & { revision: number }): Journey {
  const { revision, ...rest } = journey;
  void revision;
  return { ...rest, is_stale: journey.context_revision !== s.session.context_revision };
}

function recomputeBlockers(journey: Journey): void {
  const byId = new Map(journey.steps.map((step) => [step.id, step]));
  for (const step of journey.steps) {
    const hard = journey.dependencies.filter((d) => d.kind === "required" && d.to_step_id === step.id);
    step.blocker_step_ids = hard
      .map((d) => d.from_step_id)
      .filter((from) => byId.get(from)?.progress !== "completed");
    if (step.blocker_step_ids.length > 0) step.availability = "blocked";
    else if (step.availability === "blocked") step.availability = "ready";
  }
}

const url = (path: string) => `${API_BASE_URL}${path}`;

/** Mock answers arrive instantly; wait a little so the demo shows the agent at work. */
const AGENT_LATENCY_MS = 2600;

export const handlers = [
  http.get(url("/open-data"), () => HttpResponse.json(clone(f.openData))),
  http.get(url("/open-data/navigation-gaps"), () => HttpResponse.json(clone(f.navigationGaps))),
  http.get(url("/open-data/navigation-gaps.csv"), () => {
    const fields = ["week", "topic", "searches", "ready", "needs_clarification", "no_match", "plans", "median_seconds_to_plan"] as const;
    const lines = f.navigationGaps.rows.map((r) => fields.map((k) => r[k] ?? "").join(","));
    return new HttpResponse([fields.join(","), ...lines].join("\n"), { headers: { "Content-Type": "text/csv" } });
  }),
  http.get(url("/open-data/search"), ({ request }) => {
    const q = (new URL(request.url).searchParams.get("q") ?? "").toLowerCase();
    // Demo search over the datasets the fixtures know (the live API searches the whole mirror).
    const curated = f.openData.curated.map((c) => ({
      title: c.source.title,
      publisher: c.source.publisher,
      portal: c.source.portal,
      theme: null,
      url: c.source.url,
      last_updated: c.source.source_updated,
    }));
    const known = [...curated, ...[...f.discoverReady.results, f.serviceCard].flatMap((c) => c.related_data)];
    const words = q.split(/\s+/).filter((w) => w.length > 2).map((w) => w.replace(/s$/, ""));
    return HttpResponse.json(known.filter((d) => words.some((w) => d.title.toLowerCase().includes(w))));
  }),
  http.get(url("/health"), () =>
    HttpResponse.json({ status: "ok", contract_version: "1.0.0", knowledge_status: "demo", ai_available: false }),
  ),

  http.post(url("/sessions"), async ({ request }) => {
    const body = (await request.json()) as { locale: Session["locale"] };
    const created = clone(f.createSession);
    state = {
      session: { ...created.session, locale: body.locale, context_revision: 0 },
      journeys: new Map(),
      messages: new Map(),
      turns: new Map(),
    };
    state.session.profile = { emirate: null, residency_status: null, life_stage: null, degree_issued_outside_uae: null };
    return HttpResponse.json({ session: state.session, access_token: TOKEN }, { status: 201 });
  }),

  http.get(url("/session"), ({ request }) => {
    const s = requireAuth(request);
    return isResponse(s) ? s : HttpResponse.json(s.session);
  }),

  http.patch(url("/session"), async ({ request }) => {
    const s = requireAuth(request);
    if (isResponse(s)) return s;
    const body = (await request.json()) as { locale: Session["locale"] };
    s.session = { ...s.session, locale: body.locale };
    return HttpResponse.json(s.session);
  }),

  http.put(url("/session/profile"), async ({ request }) => {
    const s = requireAuth(request);
    if (isResponse(s)) return s;
    const profile = (await request.json()) as ProfileRequest;
    const changed = JSON.stringify(profile) !== JSON.stringify(s.session.profile);
    s.session = {
      ...s.session,
      profile,
      context_revision: s.session.context_revision + (changed ? 1 : 0),
    };
    return HttpResponse.json(s.session);
  }),

  http.delete(url("/session"), ({ request }) => {
    const s = requireAuth(request);
    if (isResponse(s)) return s;
    state = null;
    return new HttpResponse(null, { status: 204 });
  }),

  http.post(url("/discover"), async ({ request }) => {
    const s = requireAuth(request);
    if (isResponse(s)) return s;
    await delay(AGENT_LATENCY_MS);
    const body = (await request.json()) as DiscoverRequest;
    const query = body.query.toLowerCase();
    let fixture: Discovery;
    if (body.clarification_answer) fixture = clone(f.discoverClarificationAnswer);
    else if (/licen[cs]e|visa for|car|traffic/.test(query)) fixture = clone(f.discoverNoMatch);
    else if (/baby|born|newborn|birth|مولود|ولادة/.test(query)) fixture = clone(f.discoverPersona);
    else if (query.includes("certificate") && !/degree|university|bachelor|birth/.test(query))
      fixture = clone(f.discoverClarification);
    else fixture = clone(f.discoverReady);
    return HttpResponse.json({
      ...fixture,
      id: id("dis"),
      query: body.query,
      context_revision: s.session.context_revision,
      answer:
        fixture.answer ??
        (fixture.status === "ready"
          ? "Demo data: start with the services below, in this order. Each card shows what to prepare and who decides."
          : null),
    });
  }),

  http.post(url("/services/:serviceId/nearby"), async ({ request, params }) => {
    const s = requireAuth(request);
    if (isResponse(s)) return s;
    await delay(1200);
    const body = (await request.json()) as NearbyRequest;
    const near = body.location ?? { lat: 25.2048, lng: 55.2708 };
    return HttpResponse.json({
      service_id: String(params.serviceId),
      message: "Demo data: these centres and links are examples, not a live search.",
      reach: {
        contacts: [],
        centers: [
          {
            id: "demo-centre-1",
            name: "Demo service centre",
            address: "Example address",
            lat: near.lat + 0.01,
            lng: near.lng + 0.01,
            note: "Demo data",
            source: "openstreetmap",
          },
        ],
        map_query: "Tasheel centre",
      },
    });
  }),

  http.get(url("/services/:serviceId"), ({ request, params }) => {
    const s = requireAuth(request);
    if (isResponse(s)) return s;
    const card = [...f.discoverReady.results, f.serviceCard].find((c) => c.service.id === params.serviceId);
    return card ? HttpResponse.json(clone(card)) : error(404, "NOT_FOUND", "Service not found.");
  }),

  http.post(url("/journeys"), async ({ request }) => {
    const s = requireAuth(request);
    if (isResponse(s)) return s;
    await delay(AGENT_LATENCY_MS);
    const body = (await request.clone().json()) as { service_ids: string[] };
    // The demo persona's plan (newborn in Umm Al Quwain) or the degree plan.
    const base = body.service_ids.includes("birth-registration") ? f.journeyPersona : f.journey;
    const journey = { ...clone(base), id: id("jrn"), created_at: now(), updated_at: now() } as typeof f.journey;
    journey.context_revision = s.session.context_revision;
    s.journeys.set(journey.id, { ...journey, revision: s.session.context_revision });
    return HttpResponse.json(journeyView(s, s.journeys.get(journey.id)!), { status: 201 });
  }),

  http.get(url("/journeys/:journeyId"), ({ request, params }) => {
    const s = requireAuth(request);
    if (isResponse(s)) return s;
    const journey = s.journeys.get(String(params.journeyId));
    return journey ? HttpResponse.json(journeyView(s, journey)) : error(404, "NOT_FOUND", "Plan not found.");
  }),

  http.post(url("/journeys/:journeyId/replan"), async ({ request, params }) => {
    const s = requireAuth(request);
    if (isResponse(s)) return s;
    await delay(AGENT_LATENCY_MS);
    const journey = s.journeys.get(String(params.journeyId));
    if (!journey) return error(404, "NOT_FOUND", "Plan not found.");
    journey.context_revision = s.session.context_revision;
    journey.notices = [...f.journey.notices, "Demo: the plan was updated for your current profile."];
    return HttpResponse.json(journeyView(s, journey));
  }),

  http.patch(url("/journeys/:journeyId/steps/:stepId"), async ({ request, params }) => {
    const s = requireAuth(request);
    if (isResponse(s)) return s;
    const journey = s.journeys.get(String(params.journeyId));
    if (!journey) return error(404, "NOT_FOUND", "Plan not found.");
    if (journey.context_revision !== s.session.context_revision)
      return HttpResponse.json(f.errorContextStale, { status: 409 });
    const step = journey.steps.find((st) => st.id === params.stepId);
    if (!step) return error(404, "NOT_FOUND", "Step not found.");
    const body = (await request.json()) as StepUpdateRequest;
    if (body.progress === "completed" && step.blocker_step_ids.length > 0)
      return HttpResponse.json(f.errorPrerequisites, { status: 409 });
    for (const item of body.document_progress ?? []) {
      const doc = step.document_progress.find((d) => d.document_id === item.document_id);
      if (!doc) return error(422, "VALIDATION_ERROR", "Unknown document ID.");
      doc.status = item.status;
    }
    if (body.progress) step.progress = body.progress;
    recomputeBlockers(journey);
    journey.updated_at = now();
    return HttpResponse.json(journeyView(s, journey));
  }),

  http.get(url("/journeys/:journeyId/messages"), ({ request, params }) => {
    const s = requireAuth(request);
    if (isResponse(s)) return s;
    if (!s.journeys.has(String(params.journeyId))) return error(404, "NOT_FOUND", "Plan not found.");
    return HttpResponse.json({ items: s.messages.get(String(params.journeyId)) ?? [] });
  }),

  http.post(url("/journeys/:journeyId/coach"), async ({ request, params }) => {
    const s = requireAuth(request);
    if (isResponse(s)) return s;
    const journeyId = String(params.journeyId);
    const journey = s.journeys.get(journeyId);
    if (!journey) return error(404, "NOT_FOUND", "Plan not found.");
    const body = (await request.json()) as CoachRequest;
    const fingerprint = `${body.step_id}|${body.message}`;
    const previous = s.turns.get(body.client_message_id);
    if (previous) {
      return previous.fingerprint === fingerprint
        ? HttpResponse.json(previous.turn)
        : error(409, "MESSAGE_ID_CONFLICT", "This client_message_id was already used.");
    }
    if (journey.context_revision !== s.session.context_revision)
      return HttpResponse.json(f.errorContextStale, { status: 409 });
    const template = /document|need|bring|مستند/i.test(body.message) ? f.coachTurn : f.coachInsufficient;
    const turn: CoachTurn = clone(template);
    const stepId = body.step_id ?? journey.steps[0]?.id ?? null;
    turn.user_message = { ...turn.user_message, id: id("msg"), content: body.message, step_id: stepId, created_at: now() };
    turn.assistant_message = { ...turn.assistant_message, id: id("msg"), step_id: stepId, created_at: now() };
    turn.suggested_actions = turn.suggested_actions
      .filter((a) => journey.steps.some((st) => st.id === a.step_id || a.step_id === null))
      .map((a) => ({ ...a, step_id: a.step_id ? stepId : null }));
    turn.notices = ["Demo data: this is a fixed example answer, not a live response.", ...turn.notices];
    s.turns.set(body.client_message_id, { fingerprint, turn });
    s.messages.set(journeyId, [...(s.messages.get(journeyId) ?? []), turn.user_message, turn.assistant_message]);
    return HttpResponse.json(turn);
  }),

  http.post(url("/journeys/:journeyId/handoffs"), async ({ request, params }) => {
    const s = requireAuth(request);
    if (isResponse(s)) return s;
    const journey = s.journeys.get(String(params.journeyId));
    if (!journey) return error(404, "NOT_FOUND", "Plan not found.");
    if (journey.context_revision !== s.session.context_revision)
      return HttpResponse.json(f.errorContextStale, { status: 409 });
    const body = (await request.json()) as HandoffRequest;
    const step = journey.steps.find((st) => st.id === body.step_id);
    if (!step) return error(404, "NOT_FOUND", "Step not found.");
    const service = step.service_card.service;
    const target = body.kind === "official" ? service.official_url : service.support_url;
    if (!target || service.verification_status !== "verified")
      return HttpResponse.json(f.errorHandoffUnavailable, { status: 409 });
    const handoff: Handoff = {
      ...clone(f.handoff),
      id: id("hnd"),
      kind: body.kind,
      service_id: service.id,
      url: target,
      label: `${body.kind === "official" ? "Continue to" : "Get help from"} ${service.entity}`,
      created_at: now(),
    };
    return HttpResponse.json(handoff, { status: 201 });
  }),
];
