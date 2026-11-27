#!/usr/bin/env python3
"""Validate full merged v3 ABox graph against generated + extra SHACL shapes and privacy rules."""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path

from pyshacl import validate
from rdflib import Graph, Literal

REPO_ROOT = Path(__file__).resolve().parents[1]
GEN_DIR = REPO_ROOT / "gen"
GEN_SHACL = GEN_DIR / "shacl" / "poc-kb.shacl.ttl"
EXTRAS_DIR = REPO_ROOT / "src" / "shacl" / "extras"
RDF_V3_DIR = REPO_ROOT / "rdf" / "v3"
STATS_DIR = REPO_ROOT / "docs" / "stats"
VAL_OUT_DIR = GEN_DIR / "validation"
VAL_OUT_DIR.mkdir(parents=True, exist_ok=True)

MODULES = ("core", "recall", "diagnostics", "inspection", "signal", "ev_battery")
VIN_STRICT_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")
FORBIDDEN_PRED_RE = re.compile(r"(^|/|#)(vin|vehicle_id|vehicleid|cdescr|narrative|rawdialogue|dialogue)$", re.I)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            b = fh.read(1024 * 256)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def main() -> int:
    t0 = time.time()
    # 1. Load combined SHACL shapes
    sg = Graph()
    sg.parse(GEN_SHACL, format="turtle")
    extra_files = sorted(EXTRAS_DIR.glob("*.ttl"))
    for p in extra_files:
        sg.parse(p, format="turtle")

    # 2. Load all 6 v3 ABox modules
    dg = Graph()
    per_module_triples = {}
    for mod in MODULES:
        p = RDF_V3_DIR / f"{mod}.ttl"
        if not p.exists():
            print(f"ERROR: missing {p}; run `make build` first.", file=sys.stderr)
            return 1
        before = len(dg)
        dg.parse(p, format="turtle")
        per_module_triples[mod] = len(dg) - before
    parse_sec = round(time.time() - t0, 2)
    print(f"Parsed {len(dg)} ABox triples across {len(MODULES)} modules in {parse_sec}s")

    # 3. Privacy & hygiene scan across entire ABox
    vin_hits = []
    forbidden_pred_hits = []
    overlong_literals = []
    max_lit_len = 0
    for s, p, o in dg:
        ps = str(p)
        if FORBIDDEN_PRED_RE.search(ps):
            forbidden_pred_hits.append((str(s), ps))
        if isinstance(o, Literal):
            ov = str(o)
            if len(ov) > max_lit_len:
                max_lit_len = len(ov)
            if len(ov) > 400:
                overlong_literals.append((str(s), ps, len(ov)))
            if VIN_STRICT_RE.fullmatch(ov):
                vin_hits.append((str(s), ps, ov))

    # Also scan docs/stats/v3-*.json for forbidden keys or VIN strings
    json_privacy_hits = []
    for jp in sorted(STATS_DIR.glob("v3-*.json")):
        if jp.name == "v3-validation.json":
            continue
        txt = jp.read_text(encoding="utf-8", errors="replace")
        if re.search(r'"vehicle_id"\s*:', txt, re.I):
            json_privacy_hits.append(f"{jp.name}: contains key vehicle_id")
        for tok in re.findall(r'"([A-HJ-NPR-Z0-9]{17})"', txt):
            # Ignore hex/SHA hashes (64 chars) or pure digits; only exact 17-char quoted tokens
            json_privacy_hits.append(f"{jp.name}: 17-char token {tok}")

    # 4. Run full-graph pySHACL validation
    t1 = time.time()
    conforms, _, report_text = validate(
        data_graph=dg,
        shacl_graph=sg,
        inference="none",
        abort_on_first=False,
    )
    shacl_sec = round(time.time() - t1, 2)
    report_path = VAL_OUT_DIR / "shacl_report.txt"
    report_path.write_text(
        f"Conforms: {bool(conforms)}\nElapsed: {shacl_sec}s\n\n{report_text or ''}\n",
        encoding="utf-8",
    )
    print(f"pySHACL conforms={conforms} in {shacl_sec}s (report -> {report_path})")

    # 5. Generated artifact hashes & triple counts
    gen_artifacts = {}
    for rel in (
        "owl/poc-kb.owl.ttl",
        "shacl/poc-kb.shacl.ttl",
        "jsonld/poc-kb.context.jsonld",
        "jsonschema/poc-kb.schema.json",
    ):
        fp = GEN_DIR / rel
        if fp.exists():
            rec = {"path": f"gen/{rel}", "bytes": fp.stat().st_size, "sha256": sha256_file(fp)}
            if rel.endswith(".ttl"):
                tg = Graph()
                tg.parse(fp, format="turtle")
                rec["triples"] = len(tg)
            gen_artifacts[rel] = rec

    out = {
        "measured_at": "2026-11-25 Asia/Shanghai",
        "abox_total_triples": len(dg),
        "abox_per_module_incremental_triples": per_module_triples,
        "shacl_shapes_triples": len(sg),
        "shacl_extra_files": [p.name for p in extra_files],
        "pyshacl_conforms": bool(conforms),
        "pyshacl_seconds": shacl_sec,
        "parse_seconds": parse_sec,
        "privacy_scan": {
            "vin_17char_hits": len(vin_hits),
            "vin_samples": vin_hits[:5],
            "forbidden_predicate_hits": len(forbidden_pred_hits),
            "overlong_literals_gt_400": len(overlong_literals),
            "max_literal_length": max_lit_len,
            "stats_json_privacy_hits": json_privacy_hits[:10],
        },
        "generated_artifacts": gen_artifacts,
    }
    out_path = STATS_DIR / "v3-validation.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")
    print("Privacy scan:", out["privacy_scan"])

    if not conforms:
        print("SHACL VALIDATION FAILED:\n", (report_text or "")[:3000], file=sys.stderr)
        return 2
    if vin_hits or forbidden_pred_hits or overlong_literals or json_privacy_hits:
        print("PRIVACY/HYGIENE CHECK FAILED:", out["privacy_scan"], file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
