import json
import os

from flask import Blueprint, jsonify

from backend.auth import login_required
from backend.config import DATA_DIR

LEHRPLAN_DIR = os.path.join(DATA_DIR, "lehrplan")
JOBS_FILE = os.path.join(LEHRPLAN_DIR, "jobs.json")

bp = Blueprint("api_lehrplan", __name__, url_prefix="/api/lehrplan")

# The lehrplan data is static (generated from the BPL exports); parse each
# JSON file once and cache the result for the lifetime of the process.
_cache: dict[str, dict | list] = {}


def _load_json(filename):
    if filename in _cache:
        return _cache[filename]
    if not os.path.isfile(filename):
        return None
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    _cache[filename] = data
    return data


def _load_jobs():
    """Return the job metadata dict keyed by BPL code."""
    return _load_json(JOBS_FILE) or {}


def _load_lehrplan(code):
    return _load_json(os.path.join(LEHRPLAN_DIR, f"lehrplan_{code}.json"))


@bp.route("/jobs", methods=["GET"])
@login_required
def list_lehrplan_jobs():
    jobs = _load_jobs()
    result = [
        {
            "code": code,
            "name": meta.get("name"),
            "title": meta.get("title"),
            "short": meta.get("short"),
            "accent": meta.get("accent"),
            "accent_soft": meta.get("accentSoft"),
        }
        for code, meta in jobs.items()
    ]
    return jsonify({"data": result})


@bp.route("/<string:code>", methods=["GET"])
@login_required
def get_lehrplan(code):
    code = code.upper()
    tree = _load_lehrplan(code)
    if not tree or code not in tree:
        return jsonify({"error": "Lehrplan nicht gefunden."}), 404

    hkb_list = tree[code].get("handlungskompetenzbereiche") or []
    hkb_list = sorted(hkb_list, key=lambda h: h.get("ID HKB", ""))

    total_lz = 0
    total_lk = 0
    for hkb in hkb_list:
        hks = hkb.get("handlungskompetenzen") or []
        total_lk += sum(len(hk.get("lernkriterien") or []) for hk in hks)
        for hk in hks:
            for lk in hk.get("lernkriterien") or []:
                total_lz += len(lk.get("lernziele") or [])

    return jsonify(
        {
            "data": {
                "code": code,
                "job": _load_jobs().get(code, {}),
                "handlungskompetenzbereiche": hkb_list,
                "stats": {
                    "hkb_count": len(hkb_list),
                    "hk_count": sum(
                        len(h.get("handlungskompetenzen") or []) for h in hkb_list
                    ),
                    "lk_count": total_lk,
                    "lz_count": total_lz,
                },
            }
        }
    )
