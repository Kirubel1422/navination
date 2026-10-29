"""Command line tasks: python -m app.cli {validate,seed,cleanup-sessions,export-openapi,
sync-open-data}."""

import argparse
import json
import sys
from pathlib import Path

from app.core.config import API_ROOT
from app.db.session import get_sessionmaker
from app.knowledge.importer import import_bundle
from app.knowledge.seed_loader import SeedValidationError, load_seed
from app.modules.sessions.service import cleanup_expired
from app.opendata.sync import import_bundled

# Repository-level contract (apps/api -> repo root). `.parent.parent` never fails, even when the
# API runs from a shallow path such as /app inside the Docker image.
CONTRACT_PATH = API_ROOT.parent.parent / "contracts" / "openapi.json"


def export_openapi() -> dict:
    from app.main import create_app

    return create_app().openapi()


def _sync_open_data(args: argparse.Namespace) -> int:
    from app.agent.ajman import AjmanData
    from app.agent.bayanat import Bayanat
    from app.core.config import get_settings
    from app.opendata.sync import export_bundled, is_stale, run_sync

    settings = get_settings()
    with get_sessionmaker()() as db:
        import_bundled(db)
        if args.if_stale and not is_stale(db, settings.open_data_max_age_hours):
            print("Open data is fresh; nothing to do.")
            return 0
        timeout = settings.web_fetch_timeout_seconds * 3
        run = run_sync(db, Bayanat(timeout), AjmanData(timeout), index=not args.no_index)
        print(
            f"Open data sync {run.status}: {run.datasets_indexed} datasets indexed, "
            f"{run.snapshots_ok} curated datasets refreshed, {run.snapshots_failed} kept."
        )
        for note in run.notes:
            print(f"  - {note}")
        if args.export_bundle and run.snapshots_ok:
            for path in export_bundled(db):
                print(f"  wrote {path}")
    return 0 if run.status != "failed" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="navination")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="Validate seed knowledge without importing")
    sub.add_parser("seed", help="Validate and import seed knowledge (idempotent)")
    sub.add_parser("cleanup-sessions", help="Delete expired guest sessions and their data")
    od = sub.add_parser("sync-open-data", help="Refresh the open data index and curated datasets")
    od.add_argument(
        "--if-stale", action="store_true", help="Only when older than the refresh window"
    )
    od.add_argument("--no-index", action="store_true", help="Skip the catalogue index")
    od.add_argument("--export-bundle", action="store_true", help="Also write the bundled copies")
    export = sub.add_parser("export-openapi", help="Write contracts/openapi.json")
    export.add_argument("--check", action="store_true", help="Fail if the file is out of date")
    args = parser.parse_args(argv)

    if args.command in ("validate", "seed"):
        try:
            bundle = load_seed()
        except SeedValidationError as exc:
            print("Seed validation failed:", file=sys.stderr)
            for problem in exc.problems:
                print(f"  - {problem}", file=sys.stderr)
            return 1
        print(
            f"Seed valid: {len(bundle.services)} services, {len(bundle.sources)} sources, "
            f"{len(bundle.dependencies)} dependencies, {len(bundle.life_events)} life events."
        )
        if args.command == "seed":
            with get_sessionmaker()() as db:
                result = import_bundle(db, bundle)
            state = "imported" if result["changed"] else "already up to date"
            print(f"Knowledge {state} (import_id={result['import_id']}).")
            with get_sessionmaker()() as db:
                loaded = import_bundled(db)
            print(f"Open data: {loaded} bundled dataset snapshot(s) loaded.")
        return 0
    if args.command == "sync-open-data":
        return _sync_open_data(args)
    if args.command == "cleanup-sessions":
        with get_sessionmaker()() as db:
            removed = cleanup_expired(db)
        print(f"Removed {removed} expired session(s).")
        return 0
    if args.command == "export-openapi":
        rendered = json.dumps(export_openapi(), indent=2, ensure_ascii=False) + "\n"
        path = Path(CONTRACT_PATH)
        if args.check:
            current = path.read_text(encoding="utf-8") if path.exists() else ""
            if current != rendered:
                print(
                    f"{path} is out of date. Run: uv run python -m app.cli export-openapi",
                    file=sys.stderr,
                )
                return 1
            print(f"{path} is up to date.")
            return 0
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
        print(f"Wrote {path}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
