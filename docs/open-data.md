# Open data in NaviNation

NaviNation uses government open data in three ways: to **guide** people with real figures, to
**find** the right entity and dataset for any need, and to **give back** an anonymous dataset of
what people look for. Everything is cited, refreshed daily and still works when a portal is down.
The live view is the in-app page **/data** (API: `GET /api/v1/open-data`).

## Portals

| Portal | Access | Mirrored |
| --- | --- | --- |
| [Bayanat](https://bayanat.ae) (federal, FCSC) | Catalogue mirrored daily from the portal's own listing (8 requests of 500); files through the portal's download endpoint | ~3,540 datasets |
| [Ajman Data](https://data.ajman.ae) (Department of Digital Ajman) | Opendatasoft Explore API v2.1, public, no key | ~190 datasets |

Umm Al Quwain publishes its data through Bayanat; UAQ rows of federal datasets (e.g. births) are
used whenever a person's profile says they live there.

## Datasets behind the figures

Curated in `apps/api/app/opendata/datasets.yaml` (reviewed like the service catalogue).

| Dataset (Bayanat) | Publisher | Figures shown | Services |
| --- | --- | --- | --- |
| [Monthly e-services usage statistics (MoHESR)](https://bayanat.ae/en/Datasets/Dataset-info?id=fQJBLD41RKpal9tewQ5MKxrqFbsApEbxRfzeS6GW7BE) | Ministry of Higher Education and Scientific Research | Applications to recognise a qualification from abroad (73,019 in 2025), busiest and quietest months, share of MoHESR e-service use | Degree recognition, verification partner |
| [Annual Documents Attestation](https://bayanat.ae/en/Datasets/Dataset-info?id=X6j0y6NPcCRSyRTkgQozKbGPQxo6dc_s5U7PiZ5RcHs) | Ministry of Foreign Affairs and International Cooperation | Requests through UAE missions abroad (+55% in 2025), personal documents attested, most attested document types | Attestation abroad, birth-certificate attestation, degree recognition |
| [Birth 2005 - 2024](https://bayanat.ae/en/Datasets/Dataset-info?id=7Rs4FHlv2fJ_10RADFPSJj_j6esAGG35CRfmUcjBY8U) | Ministry of Health and Prevention | Births in the person's emirate (or the UAE), citizen or expatriate families, 10-year trend | Birth registration, attestation, residence permit, passport, Mabrouk Ma Yak |
| [Completed services at the Happiness Service Center (MoE)](https://bayanat.ae/en/Datasets/Dataset-info?id=1k108dXXGYl1yLSWLRoWEs6rjpcbbH46ycvvzipdY1Q) | Ministry of Education | Share of certificate-equivalence requests completed on time (labelled *older data*: to 2019) | School certificate equivalency |

Where the figures appear:

- **Service cards, plan steps and service pages** show an "In numbers" tile (figure, change vs
  the previous period, trend, linked source with the portal's update date) and **related open
  data** from the mirrored catalogues.
- **Navi** (the discovery agent and the coach) receives the same figures, personalised to the
  profile, and cites the dataset when it uses one ("December was the quietest month").
- The agent's dataset search runs on the local mirror first, then the live portal.

No dataset is invented for a service that has none (e.g. UAE PASS shows related datasets only).

## Sustainability

- **Daily refresh** in a background thread (`OPEN_DATA_SYNC`, `OPEN_DATA_MAX_AGE_HOURS`), or
  `python -m app.cli sync-open-data [--if-stale] [--export-bundle]`. A full run takes ~20 s.
- **Provenance** stored per snapshot: portal, publisher, the portal's update date, fetch time,
  checksum, origin (`live` or `bundled`). Every run is logged (`od_sync_runs`).
- **Bundled copies** (`app/opendata/bundled/`, ~350 KB incl. the catalogue index) load at seed
  time, so figures and search work on first start, offline, and through portal outages. A failed
  refresh keeps the previous copy and says so.
- **Stable keys**: Bayanat re-encrypts ids on every page view, so datasets are keyed on publisher
  and title, and resources are chosen by name and format at each sync.
- **Health**: `/api/v1/health` reports datasets indexed, snapshots and freshness.

## Giving data back: navigation gaps

`GET /api/v1/open-data/navigation-gaps` (JSON) and `/navigation-gaps.csv` publish weekly, anonymous
counts per topic: searches, clarifications, no-match results, plans made and the median time from
first search to a plan (the challenge's discovery-time KPI). No query text, session or profile is
stored. Service owners can see where guidance falls short (root cause R5).

## Findings shared with the portals

1. Bayanat has no public search API.
2. Bayanat's documented `GetDatasetResource?resourceID={GUID}` returned an empty body for every
   resource GUID found on dataset pages.
3. Bayanat dataset and resource ids change on every page view.
4. The playbook's Ajman host `api.ajman.ae` does not resolve; the API is at `data.ajman.ae`.
5. No open dataset of service-centre locations exists; centres come from OpenStreetMap.

**Data requests** (via the portals' request forms): UAE PASS sign-up volumes, Emirates ID and
residence-permit processing times, and service-centre locations with opening hours.
