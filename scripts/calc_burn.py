#!/usr/bin/env python3
"""Estimate workout calorie burn from local MET reference (stdlib only).

Formula: kcal = MET * body_weight_kg * duration_hours

Duration:
  - minutes: duration_hours = minutes / 60
  - sets: duration_hours = (sets * per_set_min) / 60
    (per_set_min from exercises.json, or --per-set-min default 2.0)

Intensity (optional): low=0.85, moderate/default=1.0, high/vigorous=1.15
applied as a multiplier on MET for the matched exercise.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


INTENSITY_MULT = {
    "low": 0.85,
    "easy": 0.85,
    "light": 0.85,
    "moderate": 1.0,
    "medium": 1.0,
    "normal": 1.0,
    "default": 1.0,
    "high": 1.15,
    "vigorous": 1.15,
    "hard": 1.15,
    "intense": 1.15,
}


def _norm(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[\s_\-]+", "", s)
    return s


def load_exercises(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "exercises" in data:
        return list(data["exercises"])
    if isinstance(data, list):
        return data
    raise SystemExit(f"Invalid exercises JSON: {path}")


def build_index(exercises: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any], str]]:
    """Return list of (normalized_key, exercise, key_kind)."""
    index: list[tuple[str, dict[str, Any], str]] = []
    for ex in exercises:
        eid = str(ex.get("id", ""))
        if eid:
            index.append((_norm(eid), ex, "id"))
        for field in ("name_zh", "name_en"):
            val = ex.get(field)
            if val:
                index.append((_norm(str(val)), ex, field))
        for alias in ex.get("aliases") or []:
            index.append((_norm(str(alias)), ex, "alias"))
    return index


def match_exercise(
    query: str, index: list[tuple[str, dict[str, Any], str]]
) -> tuple[dict[str, Any] | None, str, float]:
    """Fuzzy match: exact > contains > token overlap. Returns (ex, method, score)."""
    q = _norm(query)
    if not q:
        return None, "empty", 0.0

    # Exact
    for key, ex, kind in index:
        if key == q:
            return ex, f"exact:{kind}", 1.0

    # Substring either way
    best: tuple[dict[str, Any], str, float] | None = None
    for key, ex, kind in index:
        if not key:
            continue
        if q in key or key in q:
            score = min(len(q), len(key)) / max(len(q), len(key))
            if best is None or score > best[2]:
                best = (ex, f"substr:{kind}", score)
    if best and best[2] >= 0.45:
        return best

    # Character bigram-ish overlap for CJK / short tokens
    def grams(s: str) -> set[str]:
        if len(s) <= 1:
            return {s}
        return {s[i : i + 2] for i in range(len(s) - 1)} | set(s)

    qg = grams(q)
    for key, ex, kind in index:
        if not key:
            continue
        kg = grams(key)
        inter = len(qg & kg)
        union = len(qg | kg) or 1
        score = inter / union
        if best is None or score > best[2]:
            best = (ex, f"fuzzy:{kind}", score)
    if best and best[2] >= 0.35:
        return best
    return None, "unmatched", 0.0


def resolve_duration_hours(
    item: dict[str, Any], ex: dict[str, Any] | None, default_per_set_min: float
) -> tuple[float, str]:
    if "minutes" in item and item["minutes"] is not None:
        minutes = float(item["minutes"])
        return minutes / 60.0, f"minutes={minutes}"
    if "duration_min" in item and item["duration_min"] is not None:
        minutes = float(item["duration_min"])
        return minutes / 60.0, f"minutes={minutes}"
    if "hours" in item and item["hours"] is not None:
        hours = float(item["hours"])
        return hours, f"hours={hours}"
    if "sets" in item and item["sets"] is not None:
        sets = float(item["sets"])
        per = item.get("per_set_min")
        if per is None and ex is not None:
            per = ex.get("per_set_min")
        if per is None:
            per = default_per_set_min
        per = float(per)
        minutes = sets * per
        return minutes / 60.0, f"sets={sets}*per_set_min={per}"
    raise ValueError("need minutes, duration_min, hours, or sets")


def parse_session(raw: str) -> list[dict[str, Any]]:
    raw = raw.strip()
    if not raw:
        raise SystemExit("Empty session input")
    data = json.loads(raw)
    if isinstance(data, dict) and "exercises" in data:
        data = data["exercises"]
    if not isinstance(data, list):
        raise SystemExit("Session must be a JSON array of exercise objects")
    return data


def compute(
    exercises_path: Path,
    weight_kg: float,
    session: list[dict[str, Any]],
    default_per_set_min: float,
) -> dict[str, Any]:
    catalog = load_exercises(exercises_path)
    index = build_index(catalog)
    matched: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    total = 0.0

    for i, item in enumerate(session):
        if not isinstance(item, dict):
            unmatched.append({"index": i, "input": item, "reason": "not_object"})
            continue
        q = item.get("id") or item.get("name") or item.get("name_zh") or item.get("query")
        if not q:
            unmatched.append({"index": i, "input": item, "reason": "missing_id_or_name"})
            continue
        q = str(q)
        ex, method, score = match_exercise(q, index)
        intensity_raw = str(item.get("intensity") or "moderate").lower().strip()
        mult = INTENSITY_MULT.get(intensity_raw, 1.0)
        if ex is None:
            unmatched.append(
                {
                    "index": i,
                    "query": q,
                    "input": item,
                    "reason": "no_match",
                    "hint": "Ask user to clarify exercise name or pick from references/exercises.json",
                }
            )
            continue
        try:
            hours, dur_note = resolve_duration_hours(item, ex, default_per_set_min)
        except ValueError as e:
            unmatched.append(
                {
                    "index": i,
                    "query": q,
                    "matched_id": ex.get("id"),
                    "input": item,
                    "reason": str(e),
                }
            )
            continue
        if hours <= 0:
            unmatched.append(
                {
                    "index": i,
                    "query": q,
                    "matched_id": ex.get("id"),
                    "reason": "non_positive_duration",
                }
            )
            continue
        met = float(ex["met"]) * mult
        kcal = met * weight_kg * hours
        total += kcal
        matched.append(
            {
                "index": i,
                "query": q,
                "matched_id": ex.get("id"),
                "name_zh": ex.get("name_zh"),
                "name_en": ex.get("name_en"),
                "match_method": method,
                "match_score": round(score, 3),
                "base_met": ex.get("met"),
                "intensity": intensity_raw,
                "intensity_mult": mult,
                "effective_met": round(met, 3),
                "duration_note": dur_note,
                "duration_hours": round(hours, 4),
                "body_weight_kg": weight_kg,
                "kcal": round(kcal, 1),
            }
        )

    return {
        "ok": True,
        "formula": "kcal = MET * body_weight_kg * duration_hours",
        "body_weight_kg": weight_kg,
        "total_kcal": round(total, 1),
        "matched": matched,
        "unmatched": unmatched,
        "disclaimer": (
            "Estimate from local MET table (Compendium-inspired). "
            "Not medical advice. Confirm with user before meal recommendations."
        ),
        "exercises_json": str(exercises_path),
    }


def main(argv: list[str] | None = None) -> int:
    default_ex = (
        Path(__file__).resolve().parent.parent / "references" / "exercises.json"
    )
    p = argparse.ArgumentParser(
        prog="calc_burn.py",
        description=(
            "Estimate workout calorie burn using a local MET reference JSON. "
            "Pure Python 3 stdlib — no third-party dependencies. "
            "Output is JSON on stdout for Agent Skill consumption."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  # From argv JSON session
  python3 scripts/calc_burn.py --weight 70 \\
    '[{"name":"跑步","minutes":30},{"name":"深蹲","sets":5}]'

  # From stdin
  echo '[{"id":"hiit","minutes":20,"intensity":"high"}]' \\
    | python3 scripts/calc_burn.py --weight 65

  # Custom exercises path
  python3 scripts/calc_burn.py --exercises-json references/exercises.json \\
    --weight 72 '[{"name":"跳绳","minutes":15}]'
""",
    )
    p.add_argument(
        "--exercises-json",
        type=Path,
        default=default_ex,
        help=f"path to exercises.json (default: {default_ex})",
    )
    p.add_argument(
        "--weight",
        type=float,
        default=70.0,
        help="body weight in kg (default: 70)",
    )
    p.add_argument(
        "--per-set-min",
        type=float,
        default=2.0,
        help="fallback minutes per set when exercise has no per_set_min (default: 2.0)",
    )
    p.add_argument(
        "session",
        nargs="?",
        help='JSON array session, e.g. [{"name":"跑步","minutes":30}]. If omitted, read stdin.',
    )
    args = p.parse_args(argv)

    if args.weight <= 0:
        print(json.dumps({"ok": False, "error": "weight must be positive"}, ensure_ascii=False))
        return 2
    if not args.exercises_json.is_file():
        print(
            json.dumps(
                {"ok": False, "error": f"exercises json not found: {args.exercises_json}"},
                ensure_ascii=False,
            )
        )
        return 2

    if args.session:
        raw = args.session
    else:
        if sys.stdin.isatty():
            p.print_help()
            print(
                "\nerror: provide session JSON as argv or pipe via stdin",
                file=sys.stderr,
            )
            return 2
        raw = sys.stdin.read()

    try:
        session = parse_session(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "error": f"invalid JSON: {e}"}, ensure_ascii=False))
        return 2

    result = compute(args.exercises_json, args.weight, session, args.per_set_min)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["unmatched"] or result["matched"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
