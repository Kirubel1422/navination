"""Validation and storage of how a person can reach a service: phone contacts and centres.

The agent never invents contact details: every phone number must appear on an official page it
read in the run, and every centre must be one the places tool returned in the run.
"""

from typing import Any

from app.agent import contacts
from app.agent.drafts import ReachDraft
from app.agent.runtime import AgentContext
from app.agent.web import host_of


def check_reach(reach: ReachDraft | None, ctx: AgentContext, where: str) -> list[str]:
    if reach is None:
        return []
    problems: list[str] = []
    for index, contact in enumerate(reach.contacts):
        at = f"{where}.contacts[{index}]"
        page = ctx.read_pages.get(contact.source_ref)
        text = ctx.page_texts.get(contact.source_ref) or (
            ctx.page_texts.get(page.url) if page else None
        )
        if page is None or text is None:
            problems.append(
                f"{at}: source_ref must be a page you read with find_contacts or fetch_official_page."
            )
            continue
        if not contacts.plausible(contact.phone):
            problems.append(f"{at}: {contact.phone!r} is not a valid phone number.")
        elif not contacts.appears_in(contact.phone, [text]):
            problems.append(
                f"{at}: {contact.phone!r} does not appear on {contact.source_ref}. Copy numbers exactly "
                "from the page (use find_contacts) and never guess."
            )
        if contact.email and contact.email.lower() not in text.lower():
            problems.append(f"{at}: email {contact.email!r} does not appear on the source page.")
    for index, center in enumerate(reach.centers):
        if center.place_id not in ctx.places:
            problems.append(
                f"{where}.centers[{index}]: place_id {center.place_id!r} was not returned by "
                "find_service_centers in this run."
            )
    return problems


def store_reach(reach: ReachDraft | None, ctx: AgentContext) -> dict[str, Any] | None:
    """JSON for storage. Centres keep coordinates but never the person's own location."""
    if reach is None or not (reach.contacts or reach.centers or reach.map_query):
        return None
    stored_contacts = []
    for contact in reach.contacts:
        page = ctx.read_pages[contact.source_ref]
        stored_contacts.append(
            {
                "label": contact.label.model_dump(),
                "phone": " ".join(contact.phone.split()),
                "tel": contacts.tel_href(contact.phone),
                "email": contact.email,
                "hours": contact.hours.model_dump() if contact.hours else None,
                "source": {"url": page.url, "title": page.title, "publisher": host_of(page.url)},
            }
        )
    stored_centers = []
    for center in reach.centers:
        place = ctx.places[center.place_id]
        stored_centers.append(
            {
                "id": place.id,
                "name": place.name,
                "address": place.address or None,
                "lat": place.lat,
                "lng": place.lng,
                "note": center.note.model_dump() if center.note else None,
            }
        )
    return {
        "contacts": stored_contacts,
        "centers": stored_centers,
        "map_query": " ".join(reach.map_query.split()) if reach.map_query else None,
    }
