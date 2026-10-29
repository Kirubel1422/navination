import { apiRequest } from "./client";
import type {
  CoachRequest,
  CoachTurn,
  CreateJourneyRequest,
  CreateSessionResponse,
  DiscoverRequest,
  Discovery,
  Handoff,
  HandoffRequest,
  Health,
  Journey,
  Locale,
  MessageList,
  Nearby,
  NearbyRequest,
  ProfileRequest,
  ServiceCard,
  Session,
  StepUpdateRequest,
} from "./types";

type Auth = { token: string; signal?: AbortSignal };
/** Agent runs make several model calls; the API's own budget is 150 s (AGENT_DEADLINE_SECONDS). */
const AGENT_TIMEOUT_MS = 180_000;
const seg = encodeURIComponent;

export const api = {
  health: (signal?: AbortSignal) => apiRequest<Health>("/health", { signal }),
  createSession: (locale: Locale) =>
    apiRequest<CreateSessionResponse>("/sessions", { method: "POST", body: { locale } }),
  getSession: ({ token, signal }: Auth) => apiRequest<Session>("/session", { token, signal }),
  updateLocale: ({ token }: Auth, locale: Locale) =>
    apiRequest<Session>("/session", { method: "PATCH", token, body: { locale } }),
  replaceProfile: ({ token }: Auth, profile: ProfileRequest) =>
    apiRequest<Session>("/session/profile", { method: "PUT", token, body: profile }),
  deleteSession: ({ token }: Auth) => apiRequest<void>("/session", { method: "DELETE", token }),
  discover: ({ token, signal }: Auth, body: DiscoverRequest) =>
    apiRequest<Discovery>("/discover", { method: "POST", token, body, signal, timeoutMs: AGENT_TIMEOUT_MS }),
  getService: ({ token, signal }: Auth, serviceId: string) =>
    apiRequest<ServiceCard>(`/services/${seg(serviceId)}`, { token, signal, timeoutMs: AGENT_TIMEOUT_MS }),
  nearby: ({ token, signal }: Auth, serviceId: string, body: NearbyRequest) =>
    apiRequest<Nearby>(`/services/${seg(serviceId)}/nearby`, {
      method: "POST",
      token,
      body,
      signal,
      timeoutMs: AGENT_TIMEOUT_MS,
    }),
  createJourney: ({ token }: Auth, body: CreateJourneyRequest) =>
    apiRequest<Journey>("/journeys", { method: "POST", token, body, timeoutMs: AGENT_TIMEOUT_MS }),
  getJourney: ({ token, signal }: Auth, journeyId: string) =>
    apiRequest<Journey>(`/journeys/${seg(journeyId)}`, { token, signal }),
  replan: ({ token }: Auth, journeyId: string) =>
    apiRequest<Journey>(`/journeys/${seg(journeyId)}/replan`, {
      method: "POST",
      token,
      body: {},
      timeoutMs: AGENT_TIMEOUT_MS,
    }),
  updateStep: ({ token }: Auth, journeyId: string, stepId: string, body: StepUpdateRequest) =>
    apiRequest<Journey>(`/journeys/${seg(journeyId)}/steps/${seg(stepId)}`, {
      method: "PATCH",
      token,
      body,
    }),
  listMessages: ({ token, signal }: Auth, journeyId: string) =>
    apiRequest<MessageList>(`/journeys/${seg(journeyId)}/messages`, { token, signal }),
  coach: ({ token }: Auth, journeyId: string, body: CoachRequest) =>
    apiRequest<CoachTurn>(`/journeys/${seg(journeyId)}/coach`, {
      method: "POST",
      token,
      body,
      timeoutMs: AGENT_TIMEOUT_MS,
    }),
  createHandoff: ({ token }: Auth, journeyId: string, body: HandoffRequest) =>
    apiRequest<Handoff>(`/journeys/${seg(journeyId)}/handoffs`, { method: "POST", token, body }),
};
