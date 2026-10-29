"""A scripted, deterministic stand-in for an OpenAI-compatible model.

FOR TESTS AND OFFLINE DEMOS ONLY. It is not part of the application package and is not copied
into the Docker image. It follows the same protocol as a real model (it calls the read-only
tools first and then the submit tool), so automated tests exercise the full agent path —
tool loop, validation, guard and persistence — without a paid model. Its "judgement" is a
small keyword script and must never be presented as AI output.
"""

import json
from itertools import count
from typing import Any

from app.providers.base import AssistantTurn, ToolCall

_ids = count(1)

EDU_UNI = [
    "mohesr-degree-recognition",
    "mofa-attestation-abroad",
    "uae-pass-account",
    "degree-verification-partner",
]
EDU_SCHOOL = ["moe-school-equivalency"]
BABY = [
    "birth-registration",
    "birth-certificate-attestation",
    "newborn-passport-embassy",
    "newborn-residence-permit",
    "mabrouk-ma-yak",
]
STAGE_TITLES = [
    (
        {"en": "Get ready", "ar": "الاستعداد"},
        {"en": "Set up what later steps need.", "ar": "جهّز ما تحتاجه الخطوات اللاحقة."},
    ),
    (
        {"en": "Main applications", "ar": "الطلبات الرئيسية"},
        {"en": "Apply once the earlier steps are done.", "ar": "قدّم بعد إنجاز الخطوات السابقة."},
    ),
    (
        {"en": "Final steps", "ar": "الخطوات الأخيرة"},
        {"en": "Finish with the remaining services.", "ar": "أكمل الخدمات المتبقية."},
    ),
]
FIELDS_AR = {
    "emirate": "الإمارة",
    "residency_status": "حالة الإقامة",
    "life_stage": "المرحلة الحياتية",
    "degree_issued_outside_uae": "مكان صدور المؤهل",
}


def _call(name: str, args: dict[str, Any]) -> ToolCall:
    return ToolCall(
        id=f"call_{next(_ids)}", name=name, arguments=json.dumps(args, ensure_ascii=False)
    )


def _history(messages: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any], Any]]:
    """(tool name, arguments, parsed result) for every tool call answered so far."""
    calls: dict[str, tuple[str, dict[str, Any]]] = {}
    out = []
    for message in messages:
        if message.get("role") == "assistant":
            for call in message.get("tool_calls") or []:
                calls[call["id"]] = (
                    call["function"]["name"],
                    json.loads(call["function"]["arguments"] or "{}"),
                )
        elif message.get("role") == "tool" and message["tool_call_id"] in calls:
            name, args = calls[message["tool_call_id"]]
            try:
                result = json.loads(message["content"])
            except json.JSONDecodeError:
                result = message["content"]
            out.append((name, args, result))
    return out


def _details(history: list[tuple[str, dict[str, Any], Any]]) -> dict[str, dict[str, Any]]:
    return {
        r["service_id"]: r
        for name, _, r in history
        if name == "get_catalog_service" and isinstance(r, dict) and "service_id" in r
    }


def _assess(detail: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    reasons, missing, relevance = [], [], "potentially_relevant"
    for criterion in detail.get("criteria", []):
        rule = criterion.get("profile_rule") or criterion.get("rule")
        if not rule:
            continue
        allowed = rule.get("allowed_values", rule.get("allowed", []))
        value = profile.get(rule["field"])
        if value is None:
            missing.append(rule["field"])
            if relevance == "potentially_relevant":
                relevance = "more_information_needed"
            reasons.append(
                {
                    "text": {
                        "en": f"Not known yet: {rule['field'].replace('_', ' ')}. Criterion: {criterion['text']}",
                        "ar": f"لم نعرف بعد {FIELDS_AR[rule['field']]}. المعيار المنشور مذكور في المصدر.",
                    },
                    "source_refs": criterion["source_ids"],
                }
            )
        elif value in allowed:
            reasons.append(
                {
                    "text": {
                        "en": f"Your profile matches: {criterion['text']}",
                        "ar": "ملفك يتوافق مع هذا المعيار المنشور.",
                    },
                    "source_refs": criterion["source_ids"],
                }
            )
        else:
            relevance = "criterion_mismatch"
            reasons.append(
                {
                    "text": {
                        "en": f"Your profile may not meet: {criterion['text']}",
                        "ar": "قد لا يستوفي ملفك هذا المعيار المنشور.",
                    },
                    "source_refs": criterion["source_ids"],
                }
            )
    if not reasons:
        reasons.append(
            {
                "text": {
                    "en": f"Relevant to your need: {detail['summary']}",
                    "ar": "مرتبطة بحاجتك.",
                },
                "source_refs": (
                    detail.get("source_ids") or [s["source_id"] for s in detail.get("sources", [])]
                )[:1],
            }
        )
    return {
        "relevance": relevance,
        "reasons": reasons[:6],
        "missing_profile_fields": sorted(set(missing)),
    }


def _has(text: str, words: list[str]) -> bool:
    return any(w in text for w in words)


class ScriptedModel:
    name = "scripted-test-model"

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        response_format: dict[str, Any] | None = None,
    ) -> AssistantTurn:
        offered = {t["function"]["name"] for t in tools}
        task = (response_format or {}).get("json_schema", {}).get("name") or next(
            (n for n in offered if n.startswith("submit_")), ""
        )
        payload = json.loads(messages[1]["content"])
        if not task:  # research phase of the json_schema protocol: infer the task from the payload
            task = (
                "submit_answer"
                if "QUESTION" in payload
                else "submit_plan"
                if "SELECTED" in payload
                else "submit_assessment"
                if "SERVICE" in payload
                else "submit_discovery"
            )
        history = _history(messages)
        handler = {
            "submit_discovery": self._discovery,
            "submit_plan": self._plan,
            "submit_answer": self._coach,
            "submit_assessment": self._assessment,
        }[task]
        turn = handler(payload, history)
        submit = next((c for c in turn.tool_calls if c.name == task), None)
        if submit is None:
            return turn
        if response_format is not None:
            return AssistantTurn(content=submit.arguments)  # the strict JSON answer
        if task not in offered:
            return AssistantTurn(content="I have what I need and am ready to answer.")
        return turn

    # ------------------------------------------------------------------ discovery
    def _discovery(self, payload: dict[str, Any], history: list) -> AssistantTurn:  # type: ignore[type-arg]
        catalog = {s["service_id"]: s for s in (payload.get("CATALOG") or {}).get("services", [])}
        if not catalog and not any(name == "list_catalog_services" for name, _, _ in history):
            return AssistantTurn(None, [_call("list_catalog_services", {})])
        query = payload["REQUEST"].lower()
        answered = (payload.get("CLARIFICATION_ANSWERED") or {}).get("answer", "").lower()
        text = f"{query} {answered}"
        degree = _has(
            text,
            [
                "degree",
                "bachelor",
                "master",
                "university",
                "جامعي",
                "بكالوريوس",
                "higher education",
            ],
        )
        school = _has(text, ["school", "grade 12", "secondary", "ثانوي", "مدرس"])
        baby = _has(text, ["baby", "newborn", "born", "birth", "مولود", "ولادة"])
        certificate = _has(text, ["certificate", "شهادة"]) and not (degree or school or baby)
        if baby and degree and not answered:
            return self._submit_clarification(
                {"en": "Which situation should we plan first?", "ar": "أي حالة نخطط لها أولاً؟"},
                [
                    (
                        "education_qualification",
                        {"en": "Using my education qualification", "ar": "استخدام مؤهلي الدراسي"},
                    ),
                    ("new_baby", {"en": "Our new baby", "ar": "مولودنا الجديد"}),
                ],
            )
        if certificate and not answered:
            return self._submit_clarification(
                {
                    "en": "Which qualification do you want to use in the UAE?",
                    "ar": "ما المؤهل الذي تريد استخدامه في الإمارات؟",
                },
                [
                    ("university", {"en": "A university degree", "ar": "شهادة جامعية"}),
                    (
                        "school",
                        {
                            "en": "A school (grade 12) certificate",
                            "ar": "شهادة مدرسية (الصف الثاني عشر)",
                        },
                    ),
                ],
            )
        if baby and not (degree and "education" in answered):
            topic, label, chosen = (
                "new_baby",
                {"en": "Register a new baby", "ar": "تسجيل مولود جديد"},
                BABY,
            )
        elif school:
            topic, label, chosen = (
                "education_qualification",
                {
                    "en": "Equalise a school certificate from abroad",
                    "ar": "معادلة شهادة مدرسية من الخارج",
                },
                EDU_SCHOOL,
            )
        elif degree:
            topic, label, chosen = (
                "education_qualification",
                {
                    "en": "Get an overseas university degree recognised",
                    "ar": "الاعتراف بشهادة جامعية من الخارج",
                },
                EDU_UNI,
            )
        else:
            return AssistantTurn(
                None,
                [
                    _call(
                        "submit_discovery",
                        {
                            "status": "no_match",
                            "interpreted_need": {
                                "en": "A request NaviNation cannot match to evidence yet",
                                "ar": "طلب لا يستطيع NaviNation مطابقته بأدلة بعد",
                            },
                            "notices": [
                                {
                                    "en": "I can help with using an education qualification from abroad or registering a new baby.",
                                    "ar": "يمكنني المساعدة في استخدام مؤهل دراسي من الخارج أو تسجيل مولود جديد.",
                                }
                            ],
                        },
                    )
                ],
            )
        details = {**catalog, **_details(history)}
        missing = [sid for sid in chosen if sid not in details]
        if missing:
            return AssistantTurn(
                None, [_call("get_catalog_service", {"service_id": sid}) for sid in missing]
            )
        profile = payload.get("PROFILE") or {}
        results = []
        for sid in chosen:
            assessment = _assess(details[sid], profile)
            results.append({"kind": "catalog", "service_id": sid, "assessment": assessment})
        rank = {"potentially_relevant": 0, "more_information_needed": 1, "criterion_mismatch": 2}
        results.sort(key=lambda r: rank[r["assessment"]["relevance"]])
        return AssistantTurn(
            None,
            [
                _call(
                    "submit_discovery",
                    {
                        "status": "ready",
                        "interpreted_need": label,
                        "topic": {"id": topic, "label": label},
                        "results": results,
                    },
                )
            ],
        )

    def _submit_clarification(self, question: dict[str, str], options: list) -> AssistantTurn:  # type: ignore[type-arg]
        return AssistantTurn(
            None,
            [
                _call(
                    "submit_discovery",
                    {
                        "status": "needs_clarification",
                        "interpreted_need": {
                            "en": "Your request could mean more than one thing",
                            "ar": "قد يحتمل طلبك أكثر من معنى",
                        },
                        "clarification": {
                            "question": question,
                            "options": [{"id": oid, "label": label} for oid, label in options],
                        },
                    },
                )
            ],
        )

    # ------------------------------------------------------------------ plan
    def _plan(self, payload: dict[str, Any], history: list) -> AssistantTurn:  # type: ignore[type-arg]
        selected = payload["SELECTED"]
        catalog_ids = [s["service_id"] for s in selected if s["origin"] == "catalog"]
        details = {
            **{
                s["service_id"]: s for s in selected if s["origin"] == "catalog" and "criteria" in s
            },
            **_details(history),
        }
        missing = [sid for sid in catalog_ids if sid not in details]
        if missing:
            return AssistantTurn(
                None, [_call("get_catalog_service", {"service_id": sid}) for sid in missing]
            )
        profile = payload.get("PROFILE") or {}
        assessments = {sid: _assess(details[sid], profile) for sid in catalog_ids}
        if catalog_ids and all(
            a["relevance"] == "criterion_mismatch" for a in assessments.values()
        ):
            return AssistantTurn(
                None,
                [
                    _call(
                        "submit_plan",
                        {
                            "status": "unsupported",
                            "unsupported_reason": {
                                "en": "Your updated profile no longer matches the selected services.",
                                "ar": "لم يعد ملفك المحدّث يتوافق مع الخدمات المختارة.",
                            },
                            "title": {"en": "Plan", "ar": "خطة"},
                        },
                    )
                ],
            )
        # Layer selected services using the reviewed dependencies (both kinds) the tools returned.
        level = {s["service_id"]: 0 for s in selected}
        known_order = [  # the script's fixed notion of a sensible order
            ("uae-pass-account", "mofa-attestation-abroad"),
            ("mofa-attestation-abroad", "mohesr-degree-recognition"),
            ("degree-verification-partner", "mohesr-degree-recognition"),
            ("birth-registration", "birth-certificate-attestation"),
            ("birth-registration", "newborn-passport-embassy"),
            ("newborn-passport-embassy", "newborn-residence-permit"),
            ("birth-certificate-attestation", "newborn-residence-permit"),
        ]
        edges = {(a, b) for a, b in known_order if a in level and b in level}
        for _ in range(len(level)):
            for pre, dst in edges:
                level[dst] = max(level[dst], level[pre] + 1)
        stages: dict[int, list[dict[str, Any]]] = {}
        for item in selected:
            sid = item["service_id"]
            detail = details.get(sid)
            key = sid[:40]
            checklist = [
                {"text": {"en": d, "ar": d}, "source_refs": []}
                if isinstance(d, str)
                else {"text": {"en": d["text"], "ar": d["text"]}, "source_refs": d["source_ids"]}
                for d in (detail or item).get("documents", [])
            ]
            title = {"en": item["title"], "ar": item.get("title_ar", item["title"])}
            step = {
                "key": key,
                "service_id": sid,
                "title": title,
                "instructions": {
                    "en": f"Prepare and apply: {item['summary']}",
                    "ar": f"جهّز وقدّم: {title['ar']}",
                },
                "assessment": assessments.get(sid)
                or {
                    "relevance": "more_information_needed",
                    "reasons": [
                        {
                            "text": {
                                "en": "Found on an official website.",
                                "ar": "وُجدت في موقع رسمي.",
                            },
                            "source_refs": [],
                        }
                    ],
                },
                "checklist": checklist,
                "depends_on": [pre[:40] for pre, dst in sorted(edges) if dst == sid],
            }
            if step["depends_on"]:
                step["dependency_note"] = {
                    "en": "Do the earlier step first.",
                    "ar": "أنجز الخطوة السابقة أولاً.",
                }
            stages.setdefault(level[sid], []).append(step)
        out = []
        for index, group in enumerate(sorted(stages)):
            title, description = STAGE_TITLES[min(index, len(STAGE_TITLES) - 1)]
            out.append({"title": title, "description": description, "steps": stages[group]})
        return AssistantTurn(
            None,
            [
                _call(
                    "submit_plan",
                    {
                        "status": "planned",
                        "title": {
                            "en": f"Plan: {payload.get('INTERPRETED_NEED') or payload['REQUEST']}",
                            "ar": "خطتك",
                        },
                        "stages": out,
                    },
                )
            ],
        )

    # ------------------------------------------------------------------ coach
    def _coach(self, payload: dict[str, Any], history: list) -> AssistantTurn:  # type: ignore[type-arg]
        current = payload.get("CURRENT_STEP")
        if current and not any(name == "get_step" for name, _, _ in history):
            return AssistantTurn(None, [_call("get_step", {"step_id": current["step_id"]})])
        arabic = payload["LOCALE"] == "ar"
        question = payload["QUESTION"].lower()
        step = (
            next(
                (r for name, _, r in history if name == "get_step" and isinstance(r, dict)), current
            )
            or {}
        )
        service = step.get("service") or {}
        sources = [s["source_id"] for s in service.get("sources", [])]
        lines: list[str] = []
        actions: list[dict[str, Any]] = []
        if _has(question, ["ignore", "system prompt", "تجاهل"]):
            lines.append(
                "لا يمكنني تغيير قواعدي."
                if arabic
                else "I can't change how I work, but I can help with this step."
            )
        if _has(question, ["document", "need", "bring", "مستند", "أحتاج"]):
            items = step.get("checklist", [])
            if items:
                lines.append("قائمة التحضير:" if arabic else "Preparation checklist:")
                lines += [f"- {i['text']} ({i['user_status']})" for i in items]
            else:
                lines.append(
                    "لا تذكر مصادرنا مستندات لهذه الخطوة."
                    if arabic
                    else "Our sources don't list documents for this step."
                )
        if _has(question, ["fee", "cost", "رسوم"]):
            fee = service.get("fee_text")
            lines.append(
                ("الرسوم: " if arabic else "Fees: ")
                + (fee or ("غير مؤكدة في مصادرنا" if arabic else "not confirmed in our sources"))
            )
        if _has(question, ["attestation", "attest", "تصديق"]):
            lines.append(
                "التصديق ختم رسمي يؤكد صحة المستند لاستخدامه في الدولة."
                if arabic
                else "Attestation is an official stamp confirming a document so it can be used in the UAE."
            )
            sources = sources or ["src-mofa-attestation"]
        if _has(question, ["apply", "where", "link", "أين", "رابط"]) and service.get(
            "has_official_url"
        ):
            lines.append(
                "يمكنك المتابعة عبر الرابط الرسمي."
                if arabic
                else "You can continue through the official link."
            )
            actions.append(
                {
                    "type": "open_official",
                    "step_id": step.get("step_id"),
                    "service_id": service.get("service_id"),
                }
            )
        grounded = bool(lines) and bool(sources)
        if not lines:
            lines.append(
                "لم أجد إجابة عن ذلك في المصادر المتاحة، لذا لن أخمّن."
                if arabic
                else "I couldn't find that in the available sources, so I won't guess. Please contact the responsible entity."
            )
        return AssistantTurn(
            None,
            [
                _call(
                    "submit_answer",
                    {
                        "answer": "\n".join(lines),
                        "grounding_status": "grounded" if grounded else "insufficient_evidence",
                        "citation_refs": sources[:3] if grounded else [],
                        "suggested_actions": actions,
                    },
                )
            ],
        )

    # ------------------------------------------------------------------ assessment
    def _assessment(self, payload: dict[str, Any], history: list) -> AssistantTurn:  # type: ignore[type-arg]
        service = payload["SERVICE"]
        if service["origin"] == "catalog":
            details = _details(history)
            if "criteria" in service:
                details.setdefault(service["service_id"], service)
            if service["service_id"] not in details:
                return AssistantTurn(
                    None, [_call("get_catalog_service", {"service_id": service["service_id"]})]
                )
            assessment = _assess(details[service["service_id"]], payload.get("PROFILE") or {})
        else:
            assessment = {
                "relevance": "more_information_needed",
                "reasons": [
                    {
                        "text": {"en": "Found on an official website.", "ar": "وُجدت في موقع رسمي."},
                        "source_refs": [],
                    }
                ],
            }
        return AssistantTurn(None, [_call("submit_assessment", assessment)])
