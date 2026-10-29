import type { components } from "./schema.gen";

type Schemas = components["schemas"];

export type Health = Schemas["Health"];
export type Profile = Schemas["Profile"];
export type ProfileRequest = Schemas["ProfileRequest"];
export type Session = Schemas["Session"];
export type CreateSessionResponse = Schemas["CreateSessionResponse"];
export type Source = Schemas["Source"];
export type Requirement = Schemas["Requirement"];
export type Service = Schemas["Service"];
export type ServiceCard = Schemas["ServiceCard"];
export type Reason = Schemas["Reason"];
export type Clarification = Schemas["Clarification"];
export type ClarificationAnswer = Schemas["ClarificationAnswer"];
export type Discovery = Schemas["Discovery"];
export type DiscoverRequest = Schemas["DiscoverRequest"];
export type Dependency = Schemas["Dependency"];
export type JourneyStep = Schemas["JourneyStep"];
export type Journey = Schemas["Journey"];
export type CreateJourneyRequest = Schemas["CreateJourneyRequest"];
export type StepUpdateRequest = Schemas["StepUpdateRequest"];
export type DocumentProgress = Schemas["DocumentProgress"];
export type CoachMessage = Schemas["CoachMessage"];
export type CoachRequest = Schemas["CoachRequest"];
export type CoachTurn = Schemas["CoachTurn"];
export type SuggestedAction = Schemas["SuggestedAction"];
export type MessageList = Schemas["MessageList"];
export type Handoff = Schemas["Handoff"];
export type HandoffRequest = Schemas["HandoffRequest"];
export type ErrorEnvelope = Schemas["ErrorEnvelope"];

export type Locale = Session["locale"];
export type ProfileField = keyof Profile;
export type Relevance = ServiceCard["relevance"];
export type Progress = JourneyStep["progress"];
export type DocumentStatus = DocumentProgress["status"];
export type VerificationStatus = Service["verification_status"];
