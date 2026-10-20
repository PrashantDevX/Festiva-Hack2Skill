"""Operator-only live verification for the Gemini integration.

Run from the repository root after creating ``.env``::

    .\\.venv\\Scripts\\python.exe backend\\scripts\\verify_gemini.py

The script performs one real structured generation and, with ``--revision``,
one real revision. It never prints the API key. If no key is configured it
exits with code 2 and makes no network request.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # noqa: E402

from app import ai  # noqa: E402
from app.models import EventInput  # noqa: E402
from app.observability import metrics  # noqa: E402
from app.services import finalize_plan  # noqa: E402


def _print_metrics() -> None:
    print("Metrics (aggregate only):")
    print(json.dumps(metrics.snapshot(), indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--revision",
        action="store_true",
        help="Also make one live revision request.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override GEMINI_MODEL for this verification run.",
    )
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    if args.model:
        os.environ["GEMINI_MODEL"] = args.model
    os.environ["FESTIVA_AI_MODE"] = "live"

    if not ai.gemini_api_key():
        print(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and supply a "
            "server-side key. No request was made.",
            file=sys.stderr,
        )
        return 2

    print("Provider : google-gemini")
    print(f"Model    : {ai.gemini_model()}")
    print("Mode     : live")
    print("API key  : configured (value not printed)")
    print()

    event = EventInput.model_validate(
        {
            "description": (
                "A relaxed 30th birthday dinner for close family and friends, "
                "with a garden setting, vegetarian food, and gentle live music."
            ),
            "event_type": "Birthday",
            "event_date": "2026-12-12",
            "location": "Bengaluru",
            "guest_count": 60,
            "budget": 75000,
            "currency": "INR",
            "preferences": "Warm lighting, marigold accents, and a calm atmosphere",
            "dietary_needs": "Vegetarian; two guests avoid nuts",
            "special_requirements": "Step-free access for one guest",
        }
    )

    ai.reset_ai_state()
    try:
        content, mode = ai.generate_content(event)
        plan = finalize_plan(content, event, mode)
    except ai.AIServiceError as exc:
        print(
            f"FAILED: generation category={exc.category} "
            f"http_status={exc.http_status} message={exc}"
        )
        _print_metrics()
        return 1

    print("Generation : OK")
    print(f"Mode       : {mode}")
    print(f"Overview   : {plan.overview[:180]}")
    print(
        "Content    : "
        f"{len(plan.expenses)} expenses, {len(plan.prep_tasks)} tasks, "
        f"{len(plan.vendors)} vendors, {len(plan.schedule)} schedule items, "
        f"{len(plan.ideas)} ideas"
    )
    print(
        "Budget     : "
        f"estimated {plan.estimated_total} {event.currency} "
        f"against {event.budget} {event.currency}"
    )

    if args.revision:
        try:
            revised_event, revised_content, revised_mode = ai.revise_content(
                plan,
                "Reduce the budget by about 10 percent and keep the vegetarian "
                "menu and step-free access.",
            )
            revised = finalize_plan(
                revised_content, revised_event, revised_mode, existing=plan
            )
        except ai.AIServiceError as exc:
            print(
                f"FAILED: revision category={exc.category} "
                f"http_status={exc.http_status} message={exc}"
            )
            _print_metrics()
            return 1
        print("Revision   : OK")
        print(
            "Revised    : "
            f"budget {revised.event.budget} {revised.event.currency}, "
            f"estimated {revised.estimated_total} {revised.event.currency}, "
            f"tasks preserved={len(revised.prep_tasks) >= len(plan.prep_tasks)}"
        )

    print()
    _print_metrics()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
