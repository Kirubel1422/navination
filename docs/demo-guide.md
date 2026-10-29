# NaviNation demonstration guide

NaviNation's searches, plans, assessments and coach answers are produced by an **AI agent**, which needs an OpenAI-compatible model with tool calling. Configure it before the demo. Exact wording and ordering will vary with the model; the safeguards described below do not.

## Setup

```bash
cp .env.docker.example .env      # set AI_MODEL, AI_API_KEY (and AI_PROVIDER_BASE_URL if not OpenAI)
docker compose up                # or: pnpm install && pnpm setup:api && pnpm dev (set the same values in apps/api/.env)
```

Check http://localhost:8000/api/v1/health: `ai_available` must be `true`. For the web-beyond-the-catalog demo (step 13), also set `WEB_SEARCH_PROVIDER` and `WEB_SEARCH_API_KEY`.

## Supported example inputs

| Purpose | Input |
| --- | --- |
| Primary journey, English | `I recently arrived and need my overseas degree recognized` |
| Primary journey, Arabic | `وصلت حديثاً وأحتاج إلى الاعتراف بشهادتي الجامعية من الخارج` |
| Rephrasing (no service names) | `How can I get my bachelors from another country accepted here?` |
| Clarification (school vs university) | `My certificate from abroad needs to be accepted` |
| Clarification (two life events) | `We had a baby and I also need my degree recognized` |
| School certificate | `How do I get my foreign high school certificate equalised?` |
| Secondary journey | `We just had a baby. What do we need to register?` (Arabic: `رزقنا بمولود جديد، ما الخطوات المطلوبة؟`) |
| Unsupported | `I want to renew my driving licence` |

**Profile variation that changes guidance:**

- Set *Was your education qualification issued outside the UAE?* to **Yes**. Recognition, attestation and partner verification move from "More information needed" to "May apply to you", and the reasons cite the published criterion.
- Set it to **No**. They become "May not match your profile" but stay visible.
- For the baby journey, *Residency status* = **UAE resident** marks the Mabrouk Ma Yak bundle (nationals) as a possible mismatch. It also turns the passport → residence-permit relationship into a hard prerequisite.

## Demonstration steps (the acceptance sequence)

1. **Start.** Run the setup above. The health check shows `knowledge_status: "mixed"` (verified plus needs-review records) and `ai_available: true`.
2. **Search as a guest.** On the home page, show **Commonly requested services**, then enter the primary English input. No sign-up is required. While the agent works the page says so. Open **How the AI agent worked** to show the tools it used (catalog reads, official pages).
3. **Confirm or clarify.** Read "We understood your need as…". To show clarification, search `My certificate from abroad needs to be accepted` and choose **A university degree…**.
4. **Review cards.** Each card shows the entity, jurisdiction, verification badge, reasons, missing information, the "Who decides" notice and a **Sources** accordion (check date shown separately from the page's own update date). Open **Details and sources** for criteria, documents, fees and timing ("Not confirmed in our sources" where unpublished). The partner-verification card is labelled **Needs review**.
5. **Add a profile detail.** Open **Optional profile**, choose *Yes, issued outside the UAE* and *UAE resident*, then save. Choose **Update results for my profile**. The **What changed** panel lists each relevance change (for example, More information needed → May apply to you).
6. **Create a plan.** Untick **Set up UAE PASS…** and leave the others selected, then choose **Create my plan**. The AI agent writes the stages, step titles, instructions and checklists. If it leaves UAE PASS out, the verified-rule guard adds it back before MoFA attestation, and the plan notes say why. Stage 1 shows parallel steps (UAE PASS and partner verification). MoFA attestation is **Waiting for an earlier step**, and MoHESR recognition shows two **Suggested** (non-blocking) predecessors with explanations.
7. **Preparation and progress.** On the MoFA step, mark the original document **I have it** and the foreign-office proof **Missing**. Try setting its progress to **Done**. It is rejected with "Finish the required earlier steps…". Set UAE PASS to **Done**, then MoFA becomes ready. Progress is labelled user-reported throughout.
8. **Coach.** Choose **Ask the coach about this step** on MoFA, then ask "What documents do I need?". The AI agent looks up the step, answers with your checklist status and cites sources. It is labelled **AI agent answer**, and **How the AI agent worked** lists its tool calls. Try "What does attestation mean?" (the agent can use the reviewed glossary tool) and "Will it rain tomorrow?" (it should answer *Not enough evidence*; citations it is not allowed to make are rejected by the backend).
9. **Verified handoff.** On MoHESR recognition, choose **Get the official link**. A real link to `mohesr.gov.ae` appears with a note that you are leaving NaviNation and that opening it does not start an application. Open it explicitly. On partner verification, the same action shows that no verified destination exists.
10. **Refresh.** Reload the page. The same session, plan, progress and conversation return. The home page also offers **Open my plan**.
11. **Profile change and stale plan.** Change the emirate to Dubai. The plan is marked as changed, controls are locked and the coach is paused. Choose **Update my plan**: the agent re-plans with your new profile and previous plan, progress is kept where the step and its verified prerequisites are unchanged, and the notes say so. To show the rediscover path, set the qualification to **No** and update. If the agent judges the selection no longer fits, the API asks you to search again rather than inventing a plan.
12. **Arabic.** Choose **العربية**. The layout switches to right-to-left, AI-written content (stage and step titles, instructions, checklists, reasons) switches language without a new model call because the agent wrote both languages, new coach replies are in Arabic, and earlier messages stay in English.
13. **Secondary event and unsupported request.** Search the baby input with residency = resident. Select *Register the birth*, *Attest the baby's birth certificate* and *Issue the baby's residence permit*, untick the passport step, and create the plan. The verified rule (passport valid ≥ 6 months for a residence permit) makes the passport a required earlier step, which the guard adds if the agent left it out. Then try a request outside the catalog, such as `How do I renew my driving licence in Dubai?`. With web search configured, the agent may find the service on an official site and label it **Found by AI on an official website — not reviewed**. Without web tools, it should return an honest no-match.
14. **Clear the session.** Choose **Clear my session**, then **Delete everything**. The old token now gets 401 and the data rows are gone (covered by the automated tests).

## Mock mode

Set `NEXT_PUBLIC_API_MODE=mock` in `apps/web/.env.local` and run `pnpm dev:web`. A **Demo data** badge stays visible. Responses are the fixtures in `contracts/examples` (synthetic IDs, reviewed content), with simplified in-memory behaviour. Use mock mode for UI work only, never as evidence of backend behaviour.

## Source review coverage

All sources were opened by the team on **28 Oct 2026 (UTC)** unless marked otherwise. "Page updated" is the date shown on the page itself.

| Service record | Status | Main sources | What the sources do not confirm |
| --- | --- | --- | --- |
| Set up UAE PASS to sign in (UAE PASS) | verified | MoFA attestation page; ICP Issuing Residency Permit | Account creation steps |
| Attest a document issued outside the UAE (MoFA, missions) | verified | mofa.gov.ae/en/services/attestation; UAE Embassy Rabat attestation page (example mission) | Fees (separate Attestation Guide), processing time for mission route |
| Verify degree via authorised partner (Dataflow / QuadraBay) | **needs_review** | Gulf News report (not opened directly) | Everything; not on official pages we reviewed |
| Recognition of university qualifications from abroad (MoHESR) | verified | u.ae Student admission and qualification recognition (page updated 22 Oct 2026); MoHESR service card | Documents, fees, processing time, order relative to attestation |
| Equalise a school certificate from abroad (MoE) | verified | u.ae Equalising high school certificates (page updated 21 Oct 2026) | Fees, processing time |
| Register the birth and get the birth certificate | verified | u.ae Having a baby (page updated 30 Sep 2026) | Fees, single online destination |
| Attest the baby's birth certificate (MOHAP/DoH/DHA + MoFA) | verified | u.ae Having a baby; MoFA attestation page | Fees, processing time |
| Baby's passport from the embassy/consulate | **needs_review** | u.ae Having a baby (120-day rule); Gulf News report (embassy route) | Embassy procedures (foreign governments) |
| Baby's residence permit and Emirates ID (ICP / GDRFA) | verified | ICP Issuing Residency Permit; u.ae family residence (updated 28 Sep 2026); u.ae Having a baby | Newborn-specific document list |
| Mabrouk Ma Yak bundle (UAE nationals) | verified | u.ae Having a baby | Documents, fees |

**Required dependencies, with verified evidence only:**

- UAE PASS → MoFA online attestation (MoFA page).
- Birth registration → birth-certificate attestation (u.ae).
- Baby's passport → residence permit, when residency = resident (ICP condition: passport valid ≥ 6 months).

Every other ordering is a *suggestion* with an explanation.

## 90-day continuation outline (not implemented)

- **Days 1–30: knowledge verification.** Ask MoHESR, MoFA, MoE, ICP and the health authorities to confirm the records, especially documents, fees and the attestation-before-recognition order. Replace the news-based records with official confirmation or remove them. Add named reviewers and review dates, and set a re-check schedule.
- **Days 31–60: usability testing.** Run moderated sessions with newcomers, Arabic-first users, older users and People of Determination, plus a screen-reader audit. Measure discovery time against a baseline: the same task using u.ae search and entity websites, timed, with failures labelled. Report task success honestly.
- **Days 61–90: towards authorised integration.** Agree a governed service-catalogue feed with u.ae and TDRA (owners, change notifications), and a human-adviser handoff (contact centre or Customer Happiness Centre). Define adoption measurement with entities, because a link click is only a navigation signal. Assess privacy and responsible AI before any live model use.
