#!/usr/bin/env python3
"""Compare rebuilt Honda 2018 baseline slice against Phase 1 TRIAL-RESULTS.md without modifying tracked queries/."""
from __future__ import annotations

import json
import time
from pathlib import Path

from pyoxigraph import RdfFormat, Store
from pyshacl import validate
from rdflib import Graph, Namespace

REPO_ROOT = Path(__file__).resolve().parents[1]
STATS_PATH = REPO_ROOT / "data" / "honda-2018" / "stats.json"
ABOX_PATH = REPO_ROOT / "rdf" / "honda_2018_abox.ttl"
BASIC_SHACL = REPO_ROOT / "shapes" / "basic.shacl.ttl"
QDIR = REPO_ROOT / "queries"
OUT_PATH = REPO_ROOT / "docs" / "stats" / "v3-baseline-regression.json"

PHASE1_REFERENCE = {
    "nodes": {
        "VehicleModelYear": 2,
        "Complaint": 3210,
        "Recall": 8,
        "Investigation": 3,
        "Component": 32,
        "DTC": 47,
        "RepairStep": 46,
        "Part": 77,
        "QaThread": 301,
        "CandidateLink": 4886,
    },
    "hard_edges": {
        "investigation_to_recall_via_CAMPNO": 0,
        "dtc_to_repair_step": 46,
        "repair_step_to_part": 77,
        "hard_total": 123,
    },
    "candidate_edges": {
        "complaint_to_recall_mmy_component": 2583,
        "complaint_to_investigation_mmy_component": 1516,
        "qa_to_component_lexicon": 554,
        "complaint_to_dtc_regex_cooccur": 253,
    },
}


def pct_delta(new: int, old: int) -> float | None:
    if old == 0:
        return None if new == 0 else 100.0
    return round((new - old) / old * 100.0, 2)


def main() -> int:
    stats = json.loads(STATS_PATH.read_text(encoding="utf-8"))

    # Validate rebuilt Phase 1 ABox against Phase 1 basic.shacl.ttl
    g = Graph()
    g.parse(ABOX_PATH, format="turtle")
    sg = Graph()
    sg.parse(BASIC_SHACL, format="turtle")
    t0 = time.time()
    conforms, _, report_text = validate(data_graph=g, shacl_graph=sg, inference="none", abort_on_first=False)
    shacl_sec = round(time.time() - t0, 2)

    # Execute Phase 1 tracked queries/Q1..Q5.rq read-only via pyoxigraph (fast, never overwriting queries/)
    store = Store()
    store.load(path=str(ABOX_PATH), format=RdfFormat.TURTLE)
    q_summary = {}
    for rq in sorted(QDIR.glob("Q*.rq")):
        t1 = time.time()
        rows = list(store.query(rq.read_text(encoding="utf-8")))
        q_summary[rq.stem] = {"n": len(rows), "seconds": round(time.time() - t1, 4)}

    comparison = {"nodes": {}, "hard_edges": {}, "candidate_edges": {}}
    for section in ("nodes", "hard_edges", "candidate_edges"):
        for k, v1 in PHASE1_REFERENCE[section].items():
            v2 = stats[section].get(k)
            comparison[section][k] = {
                "phase1_v1": v1,
                "rebuilt": v2,
                "delta": None if v2 is None else v2 - v1,
                "delta_pct": None if v2 is None else pct_delta(v2, v1),
            }

    out = {
        "measured_at": "2026-11-25 Asia/Shanghai",
        "slice_script": "scripts/build_slice_honda_2018.py",
        "abox_triples": len(g),
        "basic_shacl_conforms": bool(conforms),
        "basic_shacl_seconds": shacl_sec,
        "phase1_queries_readonly": q_summary,
        "comparison_vs_phase1_trial_results": comparison,
        "notes": [
            "Complaint delta (+2.68%) reflects daily NHTSA updates in COMPLAINTS_RECEIVED_2025-2026.zip.",
            "Investigation delta (+1: DP22005) occurs because ACCORD HYBRID is folded into ACCORD; hard key investigation_to_recall_via_CAMPNO remains 0.",
            "qa_to_component_lexicon delta (+31.95%) reflects rebuilt src/mappings/zh_component_lexicon.yaml (original Phase 1 lexicon was not in Git); no tuning to force old counts.",
            "Pre-existing script note: untouched scripts/build_trial.py has an inline Q1 RDFLib slow-join and undefined ROOT on line 931; ABox/stats/review_10 outputs succeed before line 689.",
        ],
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    print(f"  ABox triples={len(g)}, basic.shacl conforms={conforms} ({shacl_sec}s)")
    print(f"  Phase 1 read-only queries: {q_summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
