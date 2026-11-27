#!/usr/bin/env python3
"""Build modular LinkML v3 ABox RDF graphs across 6 modules (rdf/v3/*.ttl).

Track 1 (anchored to Honda CR-V / Accord 2018 slice + full Tier-A reference vocabularies):
  - core.ttl: DataSource provenance, VehicleModelYear, Component (+SKOS), Complaint,
              Investigation, QaThread, and baseline CandidateLinks.
  - recall.ttl: US NHTSA + Canada Transport Canada Honda 2018 JurisdictionRecalls,
                cross-jurisdiction hard-key test (xjur_mfr_token) & window candidates
                (xjur_mmy_system_window), plus full-corpus TC<->NHTSA hard-key stats.
  - diagnostics.ttl: Full merged 12,412 DTC vocabulary, multi-OEM DtcDefinitions
                     (CodesList + Wal33D + OBDex), 132 OBD-II PIDs, slice RepairSteps/Parts,
                     dtc_make_context & dtc_pid_subsystem CandidateLinks.
  - inspection.ttl: Full UK DVSA MOT Class 4 item tree (934 groups), 4,432 RFR defects,
                    129 locations, 14 fuel types, plus privacy-preserving aggregated
                    2023 MOT cohort defect stats for Honda CR-V 2018 (k<5 suppressed).
  - signal.ttl: Selected COVESA VSS v6.1 signal tree (+W3C VSSo closeMatch),
                Honda (+Track 2 BYD/Tesla) opendbc CanMessages & CanSignals,
                component_can_message CandidateLinks.

Track 2 (EV traction battery independent subgraph sharing core/signal):
  - ev_battery.ttl: Figshare 30162841 safe-CSV cohort summaries (347 EVs, 700,582 charging
                    snippets) + Figshare/Zenodo DataCite dataset metadata aligned to
                    COVESA VSS TractionBattery signals + battery_fault_signal CandidateLinks.

Also exports:
  - rdf/v3/sample_abox.ttl: representative cross-module ABox for ROBOT HermiT consistency check.
  - docs/stats/v3-graph-stats.json: comprehensive counts, ratios, MOT cohort stats, and provenance.

Strict privacy guarantees:
  - Zero VINs, zero MOT vehicle_id, zero raw complaint narratives, zero raw QA dialogues.
  - MOT cohort cells with count < 5 are suppressed (insp:suppressed true, no insp:defectCount).
  - All string literals truncated to <= 350 chars.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import re
import sqlite3
import subprocess
import sys
import time
import zipfile
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, SKOS, XSD

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW = REPO_ROOT / "data" / "raw"
EXT = RAW / "extended"
SLICE_DIR = REPO_ROOT / "data" / "honda-2018"
MAP_DIR = REPO_ROOT / "src" / "mappings"
OUT_RDF = REPO_ROOT / "rdf" / "v3"
STATS_DIR = REPO_ROOT / "docs" / "stats"
REV_DIR = REPO_ROOT / "review"

for d in (OUT_RDF, STATS_DIR, REV_DIR):
    d.mkdir(parents=True, exist_ok=True)

CORE = Namespace("https://w3id.org/poc-kb/core/")
RECALL = Namespace("https://w3id.org/poc-kb/recall/")
DIAG = Namespace("https://w3id.org/poc-kb/diag/")
INSP = Namespace("https://w3id.org/poc-kb/insp/")
SIGNAL = Namespace("https://w3id.org/poc-kb/signal/")
EVB = Namespace("https://w3id.org/poc-kb/evb/")
VSSO = Namespace("https://github.com/w3c/vsso#")

MAX_STR = 350

HEAD_ALIASES = {
    "FUEL": "FUEL SYSTEM",
    "FUEL/PROPULSION SYSTEM": "FUEL SYSTEM",
    "ENGINE AND ENGINE COOLING": "ENGINE",
}

ZH_LABELS = {
    "FORWARD COLLISION AVOIDANCE": "前向碰撞避免/自动紧急制动",
    "FUEL SYSTEM": "燃油系统",
    "ENGINE": "发动机",
    "ELECTRICAL SYSTEM": "电气系统",
    "STEERING": "转向",
    "UNKNOWN OR OTHER": "未知或其他",
    "SERVICE BRAKES": "制动",
    "POWER TRAIN": "传动系统",
    "LANE DEPARTURE": "车道偏离",
    "VEHICLE SPEED CONTROL": "车速控制",
    "AIR BAGS": "安全气囊",
    "STRUCTURE": "车身结构",
    "VISIBILITY": "视野/玻璃",
    "SEAT BELTS": "安全带",
    "SEATS": "座椅",
    "BACK OVER PREVENTION": "倒车防撞/后视",
    "EXTERIOR LIGHTING": "外部灯光",
    "SUSPENSION": "悬挂",
    "WHEELS": "轮毂",
    "TIRES": "轮胎",
    "EQUIPMENT": "空调/附属设备",
    "ELECTRONIC STABILITY CONTROL": "电子稳定控制",
    "TRAILER HITCHES": "牵引钩/拖车装置",
}


def slug(s: str) -> str:
    out = re.sub(r"[^A-Za-z0-9._-]+", "_", (s or "").strip())
    return out.strip("_") or "na"


def clean_text(s: str | None, limit: int = MAX_STR) -> str:
    txt = re.sub(r"\s+", " ", (s or "").strip())
    if len(txt) > limit:
        txt = txt[: limit - 3].rstrip() + "..."
    return txt


def canon_head(h: str) -> str:
    h = (h or "").upper().strip()
    if not h:
        return ""
    if ":" in h:
        h = h.split(":")[0].strip()
    if "," in h:
        h = h.split(",")[0].strip()
    return HEAD_ALIASES.get(h, h)


def mk_iri(ns: Namespace, kind: str, code: str) -> URIRef:
    return URIRef(f"{str(ns)}{kind}/{slug(code)}")


def new_graph() -> Graph:
    g = Graph()
    g.bind("core", CORE)
    g.bind("recall", RECALL)
    g.bind("diag", DIAG)
    g.bind("insp", INSP)
    g.bind("signal", SIGNAL)
    g.bind("evb", EVB)
    g.bind("skos", SKOS)
    g.bind("vsso", VSSO)
    g.bind("rdfs", RDFS)
    g.bind("xsd", XSD)
    return g


def add_typed(g: Graph, uri: URIRef, cls: URIRef, label: str | None = None) -> None:
    g.add((uri, RDF.type, cls))
    g.add((uri, RDF.type, CORE.NamedThing))
    if label:
        g.add((uri, RDFS.label, Literal(clean_text(label, 180))))


def add_lit(g: Graph, s: URIRef, p: URIRef, val: Any, dtype: URIRef | None = None) -> None:
    if val is None or val == "":
        return
    if dtype is XSD.integer:
        g.add((s, p, Literal(int(val), datatype=XSD.integer)))
    elif dtype is XSD.decimal:
        g.add((s, p, Literal(Decimal(str(val)), datatype=XSD.decimal)))
    elif dtype is XSD.boolean:
        g.add((s, p, Literal(bool(val), datatype=XSD.boolean)))
    elif dtype is XSD.anyURI:
        g.add((s, p, URIRef(str(val))))
    else:
        g.add((s, p, Literal(clean_text(str(val)))))


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def tokenize_mfr_recall(s: str) -> list[str]:
    tokens = []
    for raw in re.split(r"[,;/&|]|\bAND\b", (s or "").upper()):
        t = re.sub(r"\s+", "", raw).strip(" .:-")
        if not t or t in {"NONE", "NA", "N/A", "MULTIPLECODES", "REFERTOCOMMENTS", "SEEATTACHED"}:
            continue
        if len(t) >= 2 and t not in tokens:
            tokens.append(t)
    return tokens


def parse_iso_date(s: str) -> dt.date | None:
    s = (s or "").strip()
    if re.fullmatch(r"\d{8}", s):
        try:
            return dt.date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        except ValueError:
            return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s[:10]):
        try:
            return dt.date.fromisoformat(s[:10])
        except ValueError:
            return None
    return None


def text_tokens(s: str) -> set[str]:
    stop = {
        "the", "and", "for", "that", "with", "this", "from", "may", "could", "certain",
        "vehicles", "vehicle", "honda", "accord", "cr", "hybrid", "issue", "recall",
        "on", "in", "of", "to", "a", "an", "or", "be", "is", "are", "was", "were",
        "not", "have", "has", "can", "will", "if", "by", "at", "as", "it", "their",
        "american", "motor", "co", "recalling", "canada", "transport", "replaced",
    }
    words = {w for w in re.findall(r"[a-z]{3,}", (s or "").lower()) if w not in stop}
    return words


def load_review_overrides() -> dict[str, tuple[str, str]]:
    """Load persisted human review judgments if present (working file or committed summary)."""
    for rev_file in (REV_DIR / "v3_review_samples.json", STATS_DIR / "v3-review.json"):
        if not rev_file.exists():
            continue
        try:
            data = json.loads(rev_file.read_text(encoding="utf-8"))
            out = {}
            for item in data.get("items", []):
                lid = item.get("link_id")
                st = item.get("judgment")
                rsn = item.get("reason", "")
                if lid and st in {"unreviewed", "accepted", "rejected", "uncertain"}:
                    out[lid] = (st, rsn)
            if out:
                return out
        except Exception:
            continue
    return {}


def add_candidate_link(
    g: Graph,
    link_id: str,
    frm: URIRef,
    to: URIRef,
    method: str,
    score: float,
    review_overrides: dict[str, tuple[str, str]],
    default_status: str = "unreviewed",
    matched_head: str = "",
    mismatch_flag: bool | None = None,
    note: str = "",
) -> URIRef:
    u = mk_iri(CORE, "link", link_id)
    st, ov_note = review_overrides.get(link_id, (default_status, ""))
    final_note = f"{note} | 审核: {ov_note}" if (note and ov_note) else (ov_note or note)
    add_typed(g, u, CORE.CandidateLink, f"{method} {score:.2f} {st}")
    g.add((u, CORE.fromEntity, frm))
    g.add((u, CORE.toEntity, to))
    add_lit(g, u, CORE.method, method)
    add_lit(g, u, CORE.score, f"{max(0.0, min(1.0, score)):.2f}", XSD.decimal)
    add_lit(g, u, CORE.reviewStatus, st)
    if matched_head:
        add_lit(g, u, CORE.matchedHead, matched_head)
    if mismatch_flag is not None:
        add_lit(g, u, CORE.mismatchFlag, mismatch_flag, XSD.boolean)
    if final_note:
        add_lit(g, u, CORE.note, final_note)
    return u


# ---------------- Provenance DataSources ----------------
SOURCES_SPEC = [
    ("nhtsa_cmpl", "Public Domain (U.S. Government)", "https://static.nhtsa.gov/odi/ffdd/cmpl/", "NHTSA ODI Consumer Complaints (2020-2026 slices)"),
    ("nhtsa_rcl", "Public Domain (U.S. Government)", "https://static.nhtsa.gov/odi/ffdd/rcl/FLAT_RCL_POST_2010.zip", "NHTSA ODI Recalls Post-2010"),
    ("nhtsa_inv", "Public Domain (U.S. Government)", "https://static.nhtsa.gov/odi/ffdd/inv/FLAT_INV.zip", "NHTSA ODI Defect Investigations"),
    ("tc_vrdb", "Open Government Licence - Canada", "https://opendatatc.tc.canada.ca/vrdb_full_monthly.csv", "Transport Canada Vehicle Recalls Database"),
    ("uk_mot_lookup", "UK Open Government Licence v3.0", "https://data.dft.gov.uk/anonymised-mot-test/lookup.zip", "UK DVSA MOT Class 4 lookup taxonomy & RFR definitions"),
    ("uk_mot_2023", "UK Open Government Licence v3.0", "https://data.dft.gov.uk/anonymised-mot-test/test_data/dft_test_result_2023.zip", "UK DVSA MOT 2023 anonymized test results & defect items (cohort-aggregated)"),
    ("codeslist_obd2", "CC-BY-4.0", "https://huggingface.co/datasets/CodesList/obd2-codes", "CodesList OBD-II generic DTC vocabulary"),
    ("wal33d_dtc", "MIT", "https://github.com/Wal33D/dtc-database", "Wal33D multi-OEM DTC SQLite database (33 manufacturers + generic)"),
    ("obdex_dtc", "CC0-1.0 / MIT", "https://github.com/foerbsnavi/OBDex", "OBDex reviewed generic SAE J2012 DTCs & Mode 01/09 PIDs"),
    ("mechanicdb_sample", "ODbL-1.0", "https://huggingface.co/datasets/Ichlibitiche/mechanicdb-obd2-repair-sample", "MechanicDB free sample: DTC to RepairStep and Part"),
    ("vehicle_qa", "Apache-2.0", "https://huggingface.co/datasets/wushan/vehicle_qa", "Chinese automotive after-sales Q&A (de-identified Honda slice)"),
    ("covesa_vss_61", "MPL-2.0", "https://github.com/COVESA/vehicle_signal_specification", "COVESA Vehicle Signal Specification v6.1"),
    ("w3c_vsso", "CC-BY-4.0 / Apache-2.0", "https://github.com/w3c/vsso", "W3C Vehicle Signal Specification Ontology (vss_rel_2.2)"),
    ("commaai_opendbc", "MIT", "https://github.com/commaai/opendbc", "Real-vehicle CAN DBC message/signal specs (Honda/BYD/Tesla)"),
    ("figshare_30162841", "CC-BY-4.0", "https://doi.org/10.6084/m9.figshare.30162841.v1", "Preprocessed EV battery fault dataset (347 EVs, 700,582 charging snippets CSV)"),
    ("academic_datacite", "CC-BY-4.0", "https://api.datacite.org/", "DataCite / Figshare verified CC-BY-4.0 EV BMS dataset metadata"),
]


def parse_obdex_generic_fast(obdex_dir: Path) -> list[dict]:
    """Fast line-oriented parser for OBDex *_enriched.yaml (avoids slow pure-Python YAML load of 31 MB)."""
    entries: list[dict] = []
    for yp in sorted((obdex_dir / "data" / "generic").glob("*_enriched.yaml")):
        cur: dict[str, Any] | None = None
        section = ""
        with yp.open(encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                line = raw.rstrip("\r\n")
                if line.startswith("- code:"):
                    if cur and cur.get("code"):
                        entries.append(cur)
                    code = line.split(":", 1)[1].strip().strip('"').upper()
                    cur = {"code": code, "category": "", "title_en": "", "title_de": "", "desc_en": "", "sources": []}
                    section = ""
                elif cur is None:
                    continue
                elif line.startswith("  category:"):
                    cur["category"] = line.split(":", 1)[1].strip().strip('"')
                    section = ""
                elif line.startswith("  title:"):
                    section = "title"
                elif line.startswith("  description:"):
                    section = "description"
                elif line.startswith("  sources:"):
                    section = "sources"
                elif line.startswith("  ") and not line.startswith("    ") and line.endswith(":"):
                    section = ""
                elif section == "title" and line.startswith("    en:"):
                    cur["title_en"] = line.split(":", 1)[1].strip().strip('"')
                elif section == "title" and line.startswith("    de:"):
                    cur["title_de"] = line.split(":", 1)[1].strip().strip('"')
                elif section == "description" and line.startswith("    en:"):
                    cur["desc_en"] = line.split(":", 1)[1].strip().strip('"')
                elif section == "sources" and line.startswith("    - "):
                    if len(cur["sources"]) < 2:
                        cur["sources"].append(line[6:].strip().strip('"'))
        if cur and cur.get("code"):
            entries.append(cur)
    return entries


def map_mot_severity(raw_cat: str) -> str:
    low = (raw_cat or "").strip().lower()
    if "danger" in low or low == "d":
        return "Dangerous"
    if "major" in low or low == "f":
        return "Major"
    if "minor" in low or low == "m":
        return "Minor"
    if "pre-eu" in low or "preeu" in low:
        return "PreEU"
    return "Advisory"


def map_mot_item_severity(rfr_type_code: str, dangerous_mark: str) -> str:
    code = (rfr_type_code or "").strip().upper()
    dmark = (dangerous_mark or "").strip().upper()
    if dmark in {"D", "Y", "1"} or code == "D":
        return "Dangerous"
    if code in {"F", "P"}:  # Failure or Pass after Rectification at Station (defect would have failed)
        return "Major"
    if code == "M":
        return "Minor"
    return "Advisory"


def mileage_bucket(raw_miles: str) -> str:
    s = (raw_miles or "").strip()
    if not s.isdigit():
        return "unknown_mileage"
    m = int(s)
    if m < 0 or m > 999999:
        return "unknown_mileage"
    if m < 30000:
        return "0_30k"
    if m < 60000:
        return "30k_60k"
    if m < 90000:
        return "60k_90k"
    return "90k_plus"


def stream_mot_2023_honda_2018() -> dict[str, Any]:
    """Stream UK MOT 2023 zip archives via `unzip -p` (handles Deflate64) without storing vehicle_id."""
    res_zip = EXT / "uk_mot_2023" / "dft_test_result_2023.zip"
    item_zip = EXT / "uk_mot_2023" / "dft_test_item_2023.zip"
    cache_path = EXT / "uk_mot_2023" / "honda_2018_agg_cache.json"
    if cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        cached["cell_counts"] = Counter({tuple(k.split("|")): int(v) for k, v in cached["cell_counts_str"].items()})
        return cached
    if not res_zip.exists() or not item_zip.exists():
        return {"available": False}

    t0 = time.time()
    # Pass 1: filter test_result.csv for Class 4, HONDA, first_use_date 2018, CR-V / ACCORD
    # Columns: 0:test_id|1:vehicle_id|2:test_date|3:test_class_id|4:test_type|5:test_result|6:test_mileage|7:postcode_area|8:make|9:model|10:colour|11:fuel_type|12:cylinder_capacity|13:first_use_date
    # vehicle_id (col 1) is NEVER read or stored.
    test_meta: dict[bytes, tuple[str, str]] = {}  # test_id_bytes -> (model_group, mileage_bucket)
    cohort_tests = Counter()
    cohort_outcomes = defaultdict(Counter)
    cohort_fuels = defaultdict(Counter)
    total_scanned = 0

    p1 = subprocess.Popen(["unzip", "-p", str(res_zip)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    assert p1.stdout is not None
    header_skipped = False
    for raw_line in p1.stdout:
        total_scanned += 1
        if not header_skipped:
            header_skipped = True
            continue
        if b"|HONDA|" not in raw_line or b"|2018-" not in raw_line:
            continue
        parts = raw_line.rstrip(b"\r\n").split(b"|")
        if len(parts) < 14:
            continue
        if parts[3] != b"4" or parts[8] != b"HONDA" or not parts[13].startswith(b"2018-"):
            continue
        mdl_b = parts[9].upper()
        if mdl_b.startswith(b"CR-V") or mdl_b.startswith(b"CRV"):
            mg = "CR-V"
        elif mdl_b.startswith(b"ACCORD"):
            mg = "ACCORD"
        else:
            continue
        tid = parts[0]
        bucket = mileage_bucket(parts[6].decode("ascii", errors="ignore"))
        outcome = parts[5].decode("ascii", errors="ignore")
        fuel = parts[11].decode("ascii", errors="ignore")
        test_meta[tid] = (mg, bucket)
        cohort_tests[mg] += 1
        cohort_outcomes[mg][outcome] += 1
        cohort_fuels[mg][fuel] += 1
    p1.wait()
    pass1_sec = round(time.time() - t0, 2)

    # Pass 2: stream test_item.csv matching tid in test_meta
    # Columns: 0:test_id|1:rfr_id|2:rfr_type_code|3:location_id|4:dangerous_mark
    t1 = time.time()
    cell_counts: Counter[tuple[str, str, str, str]] = Counter()  # (model_group, rfr_id, severity, mileage_bucket)
    items_matched = 0
    items_scanned = 0
    p2 = subprocess.Popen(["unzip", "-p", str(item_zip)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    assert p2.stdout is not None
    header_skipped = False
    for raw_line in p2.stdout:
        items_scanned += 1
        if not header_skipped:
            header_skipped = True
            continue
        bar = raw_line.find(b"|")
        if bar <= 0:
            continue
        tid = raw_line[:bar]
        meta = test_meta.get(tid)
        if meta is None:
            continue
        parts = raw_line.rstrip(b"\r\n").split(b"|")
        if len(parts) < 5:
            continue
        mg, bucket = meta
        rfr_id = parts[1].decode("ascii", errors="ignore").strip()
        sev = map_mot_item_severity(
            parts[2].decode("ascii", errors="ignore"),
            parts[4].decode("ascii", errors="ignore"),
        )
        if rfr_id:
            cell_counts[(mg, rfr_id, sev, bucket)] += 1
            items_matched += 1
    p2.wait()
    pass2_sec = round(time.time() - t1, 2)

    out = {
        "available": True,
        "total_result_rows_scanned": total_scanned,
        "total_item_rows_scanned": items_scanned,
        "pass1_seconds": pass1_sec,
        "pass2_seconds": pass2_sec,
        "cohort_tests": dict(cohort_tests),
        "cohort_outcomes": {k: dict(v) for k, v in cohort_outcomes.items()},
        "cohort_fuels": {k: dict(v) for k, v in cohort_fuels.items()},
        "items_matched": items_matched,
        "cell_counts_str": {"|".join(k): v for k, v in cell_counts.items()},
    }
    cache_path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    out["cell_counts"] = cell_counts
    return out


def extract_recall_oem_parts() -> dict[str, list[str]]:
    """Extract official OEM part numbers from NHTSA FLAT_RCL_POST_2010.zip for Honda 2018 slice."""
    rcl_zip = RAW / "FLAT_RCL_POST_2010.zip"
    by_camp: dict[str, list[str]] = defaultdict(list)
    honda_part_re = re.compile(r"\b(\d{5}-[A-Z0-9]{3}-[A-Z0-9]{3})\b", re.I)
    if not rcl_zip.exists():
        return by_camp
    with zipfile.ZipFile(rcl_zip) as zf:
        fn = [n for n in zf.namelist() if n.lower().endswith(".txt")][0]
        with zf.open(fn) as fh:
            for line in io.TextIOWrapper(fh, encoding="latin-1"):
                cols = line.rstrip("\r\n").split("\t")
                if len(cols) < 27:
                    continue
                if cols[2].strip().upper() != "HONDA" or cols[4].strip() != "2018":
                    continue
                mdl = cols[3].strip().upper()
                if "CR-V" not in mdl and "CRV" not in mdl and "ACCORD" not in mdl:
                    continue
                campno = cols[1].strip().upper()
                ptno_col = cols[26].strip()
                notes_col = cols[22] if len(cols) > 22 else ""
                for tok in re.split(r"[,;/\s]+", ptno_col):
                    t = tok.strip().upper()
                    if len(t) >= 5 and t not in {"NONE", "N/A", "NA", "UNKNOWN"} and t not in by_camp[campno]:
                        by_camp[campno].append(t)
                for m in honda_part_re.findall(notes_col):
                    t = m.upper()
                    if t not in by_camp[campno]:
                        by_camp[campno].append(t)
    return by_camp


def parse_dbc_file(path: Path) -> list[dict]:
    """Parse BO_ messages and SG_ signals from a DBC file."""
    messages = []
    cur = None
    bo_re = re.compile(r"^BO_\s+(\d+)\s+(\w+)\s*:\s*(\d+)\s+(\w+)")
    sg_re = re.compile(
        r"^\s+SG_\s+(\w+)\s*(?:M|m\d+)?\s*:\s*(\d+)\|(\d+)@[01][+-]\s*"
        r"\(([^,]+),([^)]+)\)\s*\[([^|]+)\|([^\]]+)\]\s*\"([^\"]*)\""
    )
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = bo_re.match(line)
        if m:
            cur = {
                "frame_id": int(m.group(1)),
                "name": m.group(2),
                "byte_length": int(m.group(3)),
                "sender": m.group(4),
                "signals": [],
            }
            messages.append(cur)
            continue
        if cur is not None:
            sm = sg_re.match(line)
            if sm:
                cur["signals"].append({
                    "name": sm.group(1),
                    "start_bit": int(sm.group(2)),
                    "bit_length": int(sm.group(3)),
                    "factor": sm.group(4).strip(),
                    "offset": sm.group(5).strip(),
                    "min": sm.group(6).strip(),
                    "max": sm.group(7).strip(),
                    "unit": sm.group(8).strip(),
                })
    return messages


def safe_decimal_str(raw: str) -> str | None:
    try:
        d = Decimal(str(raw).strip())
        if d.is_nan() or d.is_infinite():
            return None
        return format(d, "f")
    except Exception:
        return None


def main() -> int:
    t_start = time.time()
    review_overrides = load_review_overrides()

    # Load rebuilt Phase 1 slice
    slice_data = json.loads((SLICE_DIR / "slice_nhtsa_qa.json").read_text(encoding="utf-8"))
    mech = json.loads((SLICE_DIR / "mechanicdb.json").read_text(encoding="utf-8"))
    codeslist_rows = json.loads((SLICE_DIR / "dtc_codeslist.json").read_text(encoding="utf-8"))

    # Load curated SKOS / crosswalk mappings
    mot_map_cfg = load_yaml(MAP_DIR / "mot_group_to_nhtsa_head.yaml")
    tc_map_cfg = load_yaml(MAP_DIR / "tc_system_to_nhtsa_head.yaml")
    dbc_map_cfg = load_yaml(MAP_DIR / "dbc_message_to_component.yaml")
    vss_map_cfg = load_yaml(MAP_DIR / "vss_branch_to_component.yaml")
    pid_map_cfg = load_yaml(MAP_DIR / "dtc_subsystem_to_pid.yaml")

    # Module graphs
    g_core = new_graph()
    g_recall = new_graph()
    g_diag = new_graph()
    g_insp = new_graph()
    g_signal = new_graph()
    g_evb = new_graph()

    # Track stats & candidate records for human review sampling
    cand_pool: dict[str, list[dict]] = defaultdict(list)
    hard_edges = Counter()
    cand_edges = Counter()

    # =========================================================================
    # 1. CORE: DataSources, Vehicles, Components, Complaints, Investigations, QA
    # =========================================================================
    src_iris: dict[str, URIRef] = {}
    for key, lic, url, desc in SOURCES_SPEC:
        u = mk_iri(CORE, "source", key)
        src_iris[key] = u
        add_typed(g_core, u, CORE.DataSource, key)
        add_lit(g_core, u, CORE.sourceKey, key)
        add_lit(g_core, u, CORE.licenseName, lic)
        add_lit(g_core, u, CORE.complianceTier, "A")
        add_lit(g_core, u, CORE.sourceUrl, url, XSD.anyURI)
        add_lit(g_core, u, CORE.retrievedAt, "2026-11-25")
        add_lit(g_core, u, CORE.description, desc)

    veh_iris: dict[tuple[str, str, str], URIRef] = {}
    for make, model, year in (("HONDA", "CR-V", "2018"), ("HONDA", "ACCORD", "2018")):
        u = mk_iri(CORE, "vehicle", f"{make}_{model}_{year}")
        veh_iris[(make, model, year)] = u
        add_typed(g_core, u, CORE.VehicleModelYear, f"{make} {model} {year}")
        add_lit(g_core, u, CORE.make, make)
        add_lit(g_core, u, CORE.model, model)
        add_lit(g_core, u, CORE.modelYear, year)

    complaints = slice_data["complaints"]
    recalls_us_rows = slice_data["recalls"]
    invs_rows = slice_data["investigations"]
    qa_rows = slice_data["qa"]

    # Collect all canonical component heads across slice + mappings
    all_heads: set[str] = set()
    for r in complaints + recalls_us_rows + invs_rows:
        ch = canon_head(r.get("comp_head") or r.get("comp_desc") or "")
        if ch:
            all_heads.add(ch)
    for r in qa_rows:
        for h in r.get("comp_heads") or []:
            ch = canon_head(h)
            if ch:
                all_heads.add(ch)
    for cfg in (mot_map_cfg["entries"], tc_map_cfg["entries"], dbc_map_cfg["entries"], vss_map_cfg["entries"]):
        for e in cfg:
            for h in e.get("nhtsa_heads") or []:
                ch = canon_head(h)
                if ch:
                    all_heads.add(ch)

    comp_iris: dict[str, URIRef] = {}
    for h in sorted(all_heads):
        u = mk_iri(CORE, "component", h)
        comp_iris[h] = u
        add_typed(g_core, u, CORE.Component, h)
        add_lit(g_core, u, CORE.head, h)
        add_lit(g_core, u, CORE.labelEn, h)
        if h in ZH_LABELS:
            add_lit(g_core, u, CORE.labelZh, ZH_LABELS[h])

    # Fold complaints by ODINO
    by_odino = defaultdict(list)
    for r in complaints:
        by_odino[r["odino"]].append(r)

    slice_dtcs: set[str] = set()
    comp_iris_by_odino: dict[str, URIRef] = {}
    for odino, rows in sorted(by_odino.items()):
        u = mk_iri(CORE, "complaint", odino)
        comp_iris_by_odino[odino] = u
        r0 = rows[0]
        add_typed(g_core, u, CORE.Complaint, f"Complaint {odino} {r0['make']} {r0['model']} {r0['year']}")
        add_lit(g_core, u, CORE.odino, odino)
        g_core.add((u, CORE.vehicle, veh_iris[(r0["make"], r0["model"], r0["year"])]))
        g_core.add((u, CORE.fromSource, src_iris["nhtsa_cmpl"]))
        heads = sorted({canon_head(r["comp_head"]) for r in rows if canon_head(r["comp_head"])})
        for h in heads:
            g_core.add((u, CORE.hasComponent, comp_iris[h]))
        dtcs = sorted({d.upper() for r in rows for d in r.get("dtcs") or []})
        for d in dtcs:
            slice_dtcs.add(d)
            add_lit(g_core, u, CORE.mentionsDtcCode, d)
            g_core.add((u, DIAG.mentionsDtc, mk_iri(DIAG, "dtc", d)))
        add_lit(g_core, u, CORE.receivedDate, r0.get("received_date") or "")
        add_lit(g_core, u, CORE.crashFlag, r0.get("crash") or "")
        add_lit(g_core, u, CORE.fireFlag, r0.get("fire") or "")

    # Investigations
    by_act = defaultdict(list)
    for r in invs_rows:
        by_act[r["action_number"]].append(r)

    inv_iris: dict[str, URIRef] = {}
    inv_meta: dict[str, dict] = {}
    for action, rows in sorted(by_act.items()):
        u = mk_iri(CORE, "investigation", action)
        inv_iris[action] = u
        add_typed(g_core, u, CORE.Investigation, f"Investigation {action}")
        add_lit(g_core, u, CORE.actionNumber, action)
        pref = re.match(r"[A-Z]+", action)
        if pref:
            add_lit(g_core, u, CORE.actionType, pref.group(0))
        add_lit(g_core, u, CORE.subject, rows[0].get("subject") or "")
        add_lit(g_core, u, CORE.summary, rows[0].get("summary") or "")
        campnos = sorted({r["campno"] for r in rows if r.get("campno")})
        if campnos:
            add_lit(g_core, u, CORE.officialCampaignId, campnos[0])
        g_core.add((u, CORE.fromSource, src_iris["nhtsa_inv"]))
        models = sorted({(r["make"], r["model"], r["year"]) for r in rows})
        heads = sorted({canon_head(r["comp_head"]) for r in rows if canon_head(r["comp_head"])})
        for mmy in models:
            g_core.add((u, CORE.coversVehicle, veh_iris[mmy]))
        for h in heads:
            g_core.add((u, CORE.hasComponent, comp_iris[h]))
        inv_meta[action] = {"campnos": set(campnos), "models": set(models), "heads": set(heads)}

    # QA threads
    qa_iris: dict[str, URIRef] = {}
    for r in qa_rows:
        qid = r["qid"]
        u = mk_iri(CORE, "qa", qid)
        qa_iris[qid] = u
        add_typed(g_core, u, CORE.QaThread, f"QA {qid} {r['brand_raw']} {r['model_raw']}")
        add_lit(g_core, u, CORE.qid, qid)
        add_lit(g_core, u, CORE.brandRaw, r["brand_raw"])
        add_lit(g_core, u, CORE.modelRaw, r["model_raw"])
        add_lit(g_core, u, CORE.makeMapped, r["make_mapped"])
        add_lit(g_core, u, CORE.modelMapped, r["model_mapped"])
        add_lit(g_core, u, CORE.reportShort, r.get("report_short") or "")
        g_core.add((u, CORE.fromSource, src_iris["vehicle_qa"]))
        for d in r.get("dtcs") or []:
            slice_dtcs.add(d.upper())
        for h in r.get("comp_heads") or []:
            ch = canon_head(h)
            if ch in comp_iris:
                g_core.add((u, CORE.hasComponent, comp_iris[ch]))
                add_candidate_link(
                    g_core, f"qc-{qid}-{slug(ch)}", u, comp_iris[ch],
                    "qa_zh_lexicon", 0.50, review_overrides, matched_head=ch,
                )
                cand_edges["qa_zh_lexicon"] += 1

    # =========================================================================
    # 2. RECALL: US NHTSA + Canada Transport Canada Honda 2018 Recalls
    # =========================================================================
    by_camp = defaultdict(list)
    for r in recalls_us_rows:
        by_camp[r["campno"]].append(r)

    us_recall_iris: dict[str, URIRef] = {}
    us_recall_meta: dict[str, dict] = {}
    for campno, rows in sorted(by_camp.items()):
        u = mk_iri(RECALL, "recall", f"US_{campno}")
        us_recall_iris[campno] = u
        add_typed(g_recall, u, RECALL.JurisdictionRecall, f"US Recall {campno}")
        add_lit(g_recall, u, RECALL.jurisdiction, "US")
        add_lit(g_recall, u, RECALL.officialRecallId, campno)
        g_recall.add((u, CORE.fromSource, src_iris["nhtsa_rcl"]))

        mfr_tokens = []
        for r in rows:
            for t in tokenize_mfr_recall(r.get("mfr_campno") or ""):
                if t not in mfr_tokens:
                    mfr_tokens.append(t)
        for t in mfr_tokens:
            add_lit(g_recall, u, RECALL.manufacturerRecallNumber, t)

        r0 = rows[0]
        pot = (r0.get("potaff") or "").strip()
        if pot.isdigit():
            add_lit(g_recall, u, RECALL.unitsAffected, int(pot), XSD.integer)
        rdate = parse_iso_date(r0.get("rcdate") or "")
        if rdate:
            add_lit(g_recall, u, RECALL.recallDate, rdate.isoformat())
        defect = clean_text(r0.get("defect_summary") or "")
        remedy = clean_text(r0.get("corrective_action") or "")
        add_lit(g_recall, u, RECALL.defectSummary, defect)
        add_lit(g_recall, u, RECALL.correctiveAction, remedy)

        models = sorted({(r["make"], r["model"], r["year"]) for r in rows})
        heads = sorted({canon_head(r["comp_head"]) for r in rows if canon_head(r["comp_head"])})
        exacts = {(r["make"], r["model"], r["year"], r["comp_desc"]) for r in rows}
        for mmy in models:
            g_recall.add((u, CORE.coversVehicle, veh_iris[mmy]))
        for h in heads:
            g_recall.add((u, CORE.hasComponent, comp_iris[h]))

        # Hard link from Investigation if CAMPNO matches
        for act, im in inv_meta.items():
            if campno in im["campnos"]:
                g_recall.add((u, RECALL.resolvedFromInvestigation, inv_iris[act]))
                hard_edges["investigation_to_recall_via_CAMPNO"] += 1

        us_recall_meta[campno] = {
            "uri": u, "models": set(models), "heads": set(heads), "exacts": exacts,
            "mfr_tokens": set(mfr_tokens), "date": rdate,
            "defect": defect, "tokens": text_tokens(defect + " " + remedy),
        }

    # Complaint -> US Recall & Investigation & DTC CandidateLinks (in core.ttl)
    for odino, rows in sorted(by_odino.items()):
        c_uri = comp_iris_by_odino[odino]
        make, model, year = rows[0]["make"], rows[0]["model"], rows[0]["year"]
        exacts = {r["comp_desc"] for r in rows}
        heads = {canon_head(r["comp_head"]) for r in rows if canon_head(r["comp_head"])}
        for campno, meta in sorted(us_recall_meta.items()):
            if (make, model, year) not in meta["models"]:
                continue
            shared = sorted(heads & meta["heads"])
            if not shared:
                continue
            exact_hit = any((make, model, year, desc) in meta["exacts"] for desc in exacts)
            method = "mmy_comp_exact" if exact_hit else "mmy_comp_head"
            score = 0.90 if exact_hit else 0.60
            add_candidate_link(
                g_core, f"cr-{odino}-{campno}", c_uri, meta["uri"],
                method, score, review_overrides, matched_head=", ".join(shared),
            )
            cand_edges[method] += 1
        for act, im in sorted(inv_meta.items()):
            if (make, model, year) not in im["models"]:
                continue
            shared = sorted(heads & im["heads"])
            if not shared:
                continue
            add_candidate_link(
                g_core, f"ci-{odino}-{act}", c_uri, inv_iris[act],
                "mmy_comp_head", 0.60, review_overrides, matched_head=", ".join(shared),
            )
            cand_edges["complaint_to_investigation"] += 1
        seen_dtc_c = set()
        for r in rows:
            ch = canon_head(r["comp_head"])
            for d in r.get("dtcs") or []:
                du = d.upper()
                if (du, ch) in seen_dtc_c:
                    continue
                seen_dtc_c.add((du, ch))
                add_candidate_link(
                    g_core, f"cd-{odino}-{du}-{slug(ch)}", c_uri, mk_iri(DIAG, "dtc", du),
                    "dtc_regex_cooccur", 0.70, review_overrides, matched_head=ch,
                )
                cand_edges["dtc_regex_cooccur"] += 1

    # Transport Canada VRDB Honda CR-V / Accord 2018 recalls
    tc_sys_map = {e["tc_system"]: e["nhtsa_heads"] for e in tc_map_cfg["entries"]}
    tc_honda_by_id: dict[str, list[dict]] = defaultdict(list)
    with (EXT / "vrdb_full_monthly.csv").open(encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            if (r.get("MAKE_NAME_NM") or "").strip().upper() != "HONDA":
                continue
            yr = (r.get("YEAR") or "").strip().split(".")[0]
            if yr != "2018":
                continue
            mdl_raw = (r.get("MODEL_NAME_NM") or "").strip().upper()
            if "CR-V" in mdl_raw or "CRV" in mdl_raw:
                mg = "CR-V"
            elif "ACCORD" in mdl_raw:
                mg = "ACCORD"
            else:
                continue
            r["_model_group"] = mg
            tc_honda_by_id[r["RECALL_NUMBER_NUM"].strip()].append(r)

    ca_recall_meta: dict[str, dict] = {}
    for rnum, rows in sorted(tc_honda_by_id.items()):
        u = mk_iri(RECALL, "recall", f"CA_{rnum}")
        add_typed(g_recall, u, RECALL.JurisdictionRecall, f"CA Recall {rnum}")
        add_lit(g_recall, u, RECALL.jurisdiction, "CA")
        add_lit(g_recall, u, RECALL.officialRecallId, rnum)
        g_recall.add((u, CORE.fromSource, src_iris["tc_vrdb"]))

        mfr_tokens = []
        for r in rows:
            for t in tokenize_mfr_recall(r.get("MANUFACTURER_RECALL_NO_TXT") or ""):
                if t not in mfr_tokens:
                    mfr_tokens.append(t)
        for t in mfr_tokens:
            add_lit(g_recall, u, RECALL.manufacturerRecallNumber, t)

        r0 = rows[0]
        sys_type = (r0.get("SYSTEM_TYPE_ETXT") or "").strip()
        cat_type = (r0.get("CATEGORY_ETXT") or "").strip()
        add_lit(g_recall, u, RECALL.systemType, sys_type)
        add_lit(g_recall, u, RECALL.recallCategory, cat_type)
        units_s = (r0.get("UNIT_AFFECTED_NBR") or "").strip().split(".")[0]
        if units_s.isdigit():
            add_lit(g_recall, u, RECALL.unitsAffected, int(units_s), XSD.integer)
        rdate = parse_iso_date(r0.get("RECALL_DATE_DTE") or "")
        if rdate:
            add_lit(g_recall, u, RECALL.recallDate, rdate.isoformat())
        comment = clean_text(r0.get("COMMENT_ETXT") or "")
        add_lit(g_recall, u, RECALL.defectSummary, comment)
        # Check replacement notice in official comment
        rep_m = re.search(r"replaced by Transport Canada recall no\.\s*(\d{4})-?(\d{3})", r0.get("COMMENT_ETXT") or "", re.I)
        if rep_m:
            add_lit(g_recall, u, RECALL.replacesRecallId, rep_m.group(1) + rep_m.group(2))

        models = sorted({("HONDA", r["_model_group"], "2018") for r in rows})
        mapped_heads = sorted({canon_head(h) for h in tc_sys_map.get(sys_type, []) if canon_head(h) in comp_iris})
        for mmy in models:
            g_recall.add((u, CORE.coversVehicle, veh_iris[mmy]))
        for h in mapped_heads:
            g_recall.add((u, CORE.hasComponent, comp_iris[h]))

        ca_recall_meta[rnum] = {
            "uri": u, "models": set(models), "heads": set(mapped_heads),
            "mfr_tokens": set(mfr_tokens), "date": rdate,
            "sys_type": sys_type, "defect": comment, "tokens": text_tokens(comment),
        }

    # Cross-jurisdiction matching: US <-> CA on Honda 2018 slice
    xjur_hard = 0
    for campno, um in sorted(us_recall_meta.items()):
        for rnum, cm in sorted(ca_recall_meta.items()):
            shared_mfr = um["mfr_tokens"] & cm["mfr_tokens"]
            if shared_mfr:
                g_recall.add((um["uri"], RECALL.linkedByHardKeyRecall, cm["uri"]))
                g_recall.add((cm["uri"], RECALL.linkedByHardKeyRecall, um["uri"]))
                xjur_hard += 1
                hard_edges["xjur_mfr_token"] += 1
                continue
            shared_models = um["models"] & cm["models"]
            shared_heads = sorted(um["heads"] & cm["heads"])
            if not shared_models or not shared_heads:
                continue
            days_diff = abs((um["date"] - cm["date"]).days) if (um["date"] and cm["date"]) else 9999
            if days_diff > 180:
                continue
            union_t = um["tokens"] | cm["tokens"]
            jacc = (len(um["tokens"] & cm["tokens"]) / len(union_t)) if union_t else 0.0
            score = min(0.95, 0.55 + (0.20 if days_diff <= 60 else 0.10) + min(0.20, jacc * 0.8))
            lid = f"xjur-{campno}-CA_{rnum}"
            note = f"date_diff={days_diff}d, jaccard={jacc:.3f}, tc_sys={cm['sys_type']}"
            add_candidate_link(
                g_recall, lid, um["uri"], cm["uri"],
                "xjur_mmy_system_window", score, review_overrides,
                matched_head=", ".join(shared_heads), note=note,
            )
            cand_edges["xjur_mmy_system_window"] += 1
            cand_pool["xjur_mmy_system_window"].append({
                "link_id": lid, "us_recall": campno, "ca_recall": rnum,
                "shared_models": [m[1] for m in sorted(shared_models)],
                "shared_heads": shared_heads, "days_diff": days_diff, "jaccard": round(jacc, 3),
                "score": round(score, 2), "us_defect": um["defect"][:220], "ca_defect": cm["defect"][:220],
            })

    # Load verified full-corpus TC<->NHTSA hard-key stats from extended-probe-stats.json
    ext_probe = json.loads((STATS_DIR / "extended-probe-stats.json").read_text(encoding="utf-8"))
    tc_full_corpus_stats = ext_probe["track1_global_and_diagnostic_joins"]["transport_canada_recalls_vs_nhtsa"]

    # =========================================================================
    # 3. DIAGNOSTICS: Merged 12,412 DTCs, DtcDefinitions, 132 OBD PIDs, MechanicDB
    # =========================================================================
    codeslist_by = {r["code"].strip().upper(): r for r in codeslist_rows if r.get("code")}
    mech_codes = {str(r.get("dtc_code") or "").strip().upper(): r for r in mech["dtc_codes"] if r.get("dtc_code")}
    obdex_entries = parse_obdex_generic_fast(EXT / "obdex")
    obdex_by = {e["code"]: e for e in obdex_entries}

    # Read Wal33D SQLite
    con = sqlite3.connect(str(EXT / "wal33d_dtc_codes.db"))
    wal_rows = list(con.execute("SELECT code, manufacturer, description, type, is_generic FROM dtc_definitions"))
    con.close()
    wal_by_code: dict[str, list[tuple[str, str, str, int]]] = defaultdict(list)
    for code, mfr, desc, typ, is_gen in wal_rows:
        c = (code or "").strip().upper()
        if c:
            wal_by_code[c].append(((mfr or "GENERIC").strip().upper(), desc or "", typ or "", int(is_gen or 0)))

    # Union of all compliant Tier-A codes + slice extracted codes + NHTSA Top-20 showcase codes (C1391, C2200, P1326)
    all_dtc_codes = (
        set(codeslist_by)
        | set(wal_by_code)
        | set(obdex_by)
        | slice_dtcs
        | {"P1326", "C1391", "C2200"}
    )

    dtc_iris: dict[str, URIRef] = {}
    def_count = 0
    defs_by_code: dict[str, list[dict]] = defaultdict(list)

    for code in sorted(all_dtc_codes):
        u = mk_iri(DIAG, "dtc", code)
        dtc_iris[code] = u
        add_typed(g_diag, u, DIAG.DTC, code)
        add_lit(g_diag, u, DIAG.code, code)
        add_lit(g_diag, u, DIAG.codeFamily, code[0])
        is_gen_code = len(code) >= 2 and code[1] in {"0", "2"}
        add_lit(g_diag, u, DIAG.isGenericCode, is_gen_code, XSD.boolean)
        add_lit(g_diag, u, DIAG.inCodesList, code in codeslist_by, XSD.boolean)
        add_lit(g_diag, u, DIAG.inWal33d, code in wal_by_code, XSD.boolean)
        add_lit(g_diag, u, DIAG.inObdex, code in obdex_by, XSD.boolean)
        add_lit(g_diag, u, DIAG.inMechanicSample, code in mech_codes, XSD.boolean)

        # DtcDefinition from CodesList (GENERIC)
        if code in codeslist_by:
            cl = codeslist_by[code]
            du = mk_iri(DIAG, "dtc-def", f"{code}__GENERIC__codeslist")
            add_typed(g_diag, du, DIAG.DtcDefinition, f"{code} (GENERIC / CodesList)")
            g_diag.add((du, DIAG.definesCode, u))
            g_diag.add((u, DIAG.hasDefinition, du))
            add_lit(g_diag, du, DIAG.makeContext, "GENERIC")
            add_lit(g_diag, du, CORE.description, cl.get("description") or "")
            add_lit(g_diag, du, DIAG.category, cl.get("category") or "")
            add_lit(g_diag, du, DIAG.isGenericDefinition, True, XSD.boolean)
            g_diag.add((du, CORE.fromSource, src_iris["codeslist_obd2"]))
            def_count += 1
            defs_by_code[code].append({"uri": du, "make": "GENERIC", "source": "codeslist", "desc": clean_text(cl.get("description") or "", 140)})

        # DtcDefinitions from Wal33D (GENERIC + 33 OEMs)
        seen_wal_mfr = set()
        for mfr, desc, typ, is_gen in wal_by_code.get(code, []):
            if mfr in seen_wal_mfr:
                continue
            seen_wal_mfr.add(mfr)
            du = mk_iri(DIAG, "dtc-def", f"{code}__{mfr}__wal33d")
            add_typed(g_diag, du, DIAG.DtcDefinition, f"{code} ({mfr} / Wal33D)")
            g_diag.add((du, DIAG.definesCode, u))
            g_diag.add((u, DIAG.hasDefinition, du))
            add_lit(g_diag, du, DIAG.makeContext, mfr)
            add_lit(g_diag, du, CORE.description, desc)
            add_lit(g_diag, du, DIAG.category, typ)
            add_lit(g_diag, du, DIAG.isGenericDefinition, bool(is_gen or mfr == "GENERIC"), XSD.boolean)
            g_diag.add((du, CORE.fromSource, src_iris["wal33d_dtc"]))
            def_count += 1
            defs_by_code[code].append({"uri": du, "make": mfr, "source": "wal33d", "desc": clean_text(desc, 140)})

        # DtcDefinition from OBDex (reviewed GENERIC + DE + reference URL)
        if code in obdex_by:
            oe = obdex_by[code]
            du = mk_iri(DIAG, "dtc-def", f"{code}__GENERIC__obdex")
            add_typed(g_diag, du, DIAG.DtcDefinition, f"{code} (GENERIC / OBDex)")
            g_diag.add((du, DIAG.definesCode, u))
            g_diag.add((u, DIAG.hasDefinition, du))
            add_lit(g_diag, du, DIAG.makeContext, "GENERIC")
            add_lit(g_diag, du, DIAG.titleEn, oe.get("title_en") or "")
            add_lit(g_diag, du, DIAG.titleDe, oe.get("title_de") or "")
            add_lit(g_diag, du, CORE.description, oe.get("desc_en") or oe.get("title_en") or "")
            add_lit(g_diag, du, DIAG.category, oe.get("category") or "")
            add_lit(g_diag, du, DIAG.isGenericDefinition, True, XSD.boolean)
            for s_url in oe.get("sources", [])[:1]:
                add_lit(g_diag, du, DIAG.referenceUrl, s_url)
            g_diag.add((du, CORE.fromSource, src_iris["obdex_dtc"]))
            def_count += 1
            defs_by_code[code].append({"uri": du, "make": "GENERIC", "source": "obdex", "desc": clean_text(oe.get("title_en") or "", 140)})

    # MechanicDB RepairSteps & Parts for slice DTCs
    fix_by_id = {str(r["fix_id"]): r for r in mech["fixes"] if r.get("fix_id") is not None}
    code_to_fixes = defaultdict(list)
    for r in mech["joined"]:
        c = str(r.get("dtc_code") or "").strip().upper()
        fid = str(r.get("fix_id") or "").strip()
        if c and fid and fid not in code_to_fixes[c]:
            code_to_fixes[c].append(fid)
    part_by_id = {str(r["part_id"]): r for r in mech["parts"] if r.get("part_id") is not None}
    fix_to_parts = defaultdict(list)
    for r in mech["parts"]:
        fid = str(r.get("fix_id") or "").strip()
        pid = str(r.get("part_id") or "").strip()
        if fid and pid and pid not in fix_to_parts[fid]:
            fix_to_parts[fid].append(pid)

    part_iris: dict[str, URIRef] = {}
    step_count = 0
    for code in sorted(slice_dtcs):
        if code not in code_to_fixes:
            continue
        du = dtc_iris[code]
        for fid in code_to_fixes[code]:
            fx = fix_by_id.get(fid) or {}
            su = mk_iri(DIAG, "repair-step", fid)
            title = clean_text(fx.get("fix_title") or fid, 180)
            add_typed(g_diag, su, DIAG.RepairStep, title)
            add_lit(g_diag, su, DIAG.fixId, fid)
            add_lit(g_diag, su, DIAG.title, title)
            add_lit(g_diag, su, DIAG.difficulty, fx.get("difficulty_level") or "")
            lh = safe_decimal_str(fx.get("est_labor_hours") or "")
            if lh is not None:
                add_lit(g_diag, su, DIAG.laborHours, lh, XSD.decimal)
            g_diag.add((su, DIAG.forDtc, du))
            g_diag.add((su, CORE.fromSource, src_iris["mechanicdb_sample"]))
            step_count += 1
            hard_edges["dtc_to_repair_step"] += 1
            for pid in fix_to_parts.get(fid, []):
                pr = part_by_id.get(pid) or {}
                if pid not in part_iris:
                    pu = mk_iri(DIAG, "part", pid)
                    part_iris[pid] = pu
                    pname = clean_text(pr.get("part_name") or pid, 160)
                    add_typed(g_diag, pu, DIAG.Part, pname)
                    add_lit(g_diag, pu, DIAG.partName, pname)
                    g_diag.add((pu, CORE.fromSource, src_iris["mechanicdb_sample"]))
                g_diag.add((su, DIAG.usesPart, part_iris[pid]))
                hard_edges["repair_step_to_part"] += 1

    # Official recall OEM parts (NHTSA RCL MFR_COMP_PTNO)
    rcl_parts = extract_recall_oem_parts()
    rcl_part_count = 0
    for campno, ptlist in sorted(rcl_parts.items()):
        if campno not in us_recall_iris:
            continue
        for ptno in ptlist:
            pu = mk_iri(DIAG, "part", f"OEM_{ptno}")
            if f"OEM_{ptno}" not in part_iris:
                part_iris[f"OEM_{ptno}"] = pu
                add_typed(g_diag, pu, DIAG.Part, f"Honda OEM Part {ptno}")
                add_lit(g_diag, pu, DIAG.partName, f"Honda OEM Recall Part {ptno}")
                add_lit(g_diag, pu, DIAG.oemPartNumber, ptno)
                g_diag.add((pu, CORE.fromSource, src_iris["nhtsa_rcl"]))
                rcl_part_count += 1
            g_recall.add((us_recall_iris[campno], RDFS.seeAlso, pu))

    # dtc_make_context CandidateLinks for slice DTCs + P1326 showcase (scored against HONDA)
    dtc_context_targets = sorted(slice_dtcs | {"P1326"})
    for code in dtc_context_targets:
        du = dtc_iris[code]
        for dinfo in defs_by_code.get(code, []):
            mk = dinfo["make"]
            if mk == "HONDA":
                score, mm, note = 0.90, False, "Exact HONDA makeContext match"
            elif mk == "GENERIC":
                score, mm, note = 0.70, False, f"SAE generic definition ({dinfo['source']})"
            else:
                score, mm, note = 0.20, True, f"Cross-OEM mismatch: {mk} definition vs HONDA context"
            lid = f"dmc-{code}-{mk}-{dinfo['source']}"
            add_candidate_link(
                g_diag, lid, du, dinfo["uri"],
                "dtc_make_context", score, review_overrides,
                mismatch_flag=mm, note=note,
            )
            cand_edges["dtc_make_context"] += 1
            cand_pool["dtc_make_context"].append({
                "link_id": lid, "code": code, "makeContext": mk, "source": dinfo["source"],
                "score": score, "mismatch": mm, "desc": dinfo["desc"],
            })

    # OBDex 132 Mode 01 & Mode 09 PIDs
    pid_iris: dict[str, URIRef] = {}
    pid_to_vss = pid_map_cfg.get("pid_to_vss") or {}
    for pfn in ("mode01.yaml", "mode09.yaml"):
        plist = load_yaml(EXT / "obdex" / "data" / "pids" / pfn) or []
        for entry in plist:
            mode = str(entry.get("mode") or "").strip().zfill(2)
            pid_hex = str(entry.get("pid") or "").strip().upper()
            key = f"{mode}-{pid_hex}"
            pu = mk_iri(DIAG, "pid", f"{mode}_{pid_hex}")
            pid_iris[key] = pu
            name_obj = entry.get("name") or {}
            name_en = clean_text(name_obj.get("en") if isinstance(name_obj, dict) else str(name_obj), 160)
            name_de = clean_text(name_obj.get("de") if isinstance(name_obj, dict) else "", 160)
            add_typed(g_diag, pu, DIAG.ObdPid, f"OBD PID {key}: {name_en}")
            add_lit(g_diag, pu, DIAG.obdMode, mode)
            add_lit(g_diag, pu, DIAG.pidHex, pid_hex)
            add_lit(g_diag, pu, DIAG.pidNameEn, name_en)
            add_lit(g_diag, pu, DIAG.pidNameDe, name_de)
            if entry.get("bytes") is not None and str(entry.get("bytes")).isdigit():
                add_lit(g_diag, pu, DIAG.dataBytes, int(entry["bytes"]), XSD.integer)
            if entry.get("formula"):
                add_lit(g_diag, pu, DIAG.formula, str(entry["formula"]))
            if entry.get("unit"):
                add_lit(g_diag, pu, CORE.unit, str(entry["unit"]))
            rng = entry.get("range")
            if isinstance(rng, list) and len(rng) == 2:
                mn, mx = safe_decimal_str(rng[0]), safe_decimal_str(rng[1])
                if mn is not None:
                    add_lit(g_diag, pu, CORE.minValue, mn, XSD.decimal)
                if mx is not None:
                    add_lit(g_diag, pu, CORE.maxValue, mx, XSD.decimal)
            if key in pid_to_vss:
                g_diag.add((pu, SKOS.closeMatch, mk_iri(SIGNAL, "vss", pid_to_vss[key])))
            g_diag.add((pu, CORE.fromSource, src_iris["obdex_dtc"]))

    # dtc_pid_subsystem CandidateLinks for slice DTCs + P1326
    pid_rules = sorted(pid_map_cfg["rules"], key=lambda x: -len(x["dtc_prefix"]))
    for code in sorted(slice_dtcs | {"P1326"}):
        matched_rule = next((r for r in pid_rules if code.startswith(r["dtc_prefix"])), None)
        if not matched_rule:
            continue
        score = float(matched_rule["score"])
        for pid_key in matched_rule["pids"]:
            if pid_key not in pid_iris:
                continue
            lid = f"dpid-{code}-{pid_key}"
            add_candidate_link(
                g_diag, lid, dtc_iris[code], pid_iris[pid_key],
                "dtc_pid_subsystem", score, review_overrides,
                note=f"J2012 {matched_rule['dtc_prefix']}xx -> {matched_rule['subsystem_name']}",
            )
            cand_edges["dtc_pid_subsystem"] += 1
            cand_pool["dtc_pid_subsystem"].append({
                "link_id": lid, "code": code, "pid": pid_key,
                "subsystem": matched_rule["subsystem_name"], "score": score,
            })

    # =========================================================================
    # 4. INSPECTION: UK DVSA MOT Class 4 Taxonomy + 2023 Aggregated Cohort Stats
    # =========================================================================
    mot_group_iris: dict[str, URIRef] = {}
    mot_defect_iris: dict[str, URIRef] = {}
    mot_map_by_id = {str(e["mot_item_id"]): e for e in mot_map_cfg["entries"]}

    with zipfile.ZipFile(EXT / "uk_mot_lookup.zip") as zf:
        # item_group.csv (Class 4)
        grp_rows = [
            r for r in csv.DictReader(io.StringIO(zf.read("item_group.csv").decode("utf-8", errors="replace")), delimiter="|")
            if r.get("test_class_id") == "4"
        ]
        parent_map = {r["test_item_id"]: r["parent_id"] for r in grp_rows}

        def calc_depth(tid: str) -> int:
            d, cur, seen = 0, tid, set()
            while cur and cur != "0" and cur not in seen:
                seen.add(cur)
                p = parent_map.get(cur, "0")
                if p == cur:
                    break
                cur = p
                d += 1
            return d

        for r in grp_rows:
            tid = r["test_item_id"].strip()
            if tid == "0":
                continue
            u = mk_iri(INSP, "mot-group", f"c4_{tid}")
            mot_group_iris[tid] = u
            iname = clean_text(r["item_name"], 180)
            add_typed(g_insp, u, INSP.MotItemGroup, f"MOT C4 {tid}: {iname}")
            add_lit(g_insp, u, INSP.testItemId, tid)
            add_lit(g_insp, u, INSP.testClassId, "4")
            add_lit(g_insp, u, INSP.itemName, iname)
            add_lit(g_insp, u, INSP.hierarchyDepth, calc_depth(tid), XSD.integer)
            g_insp.add((u, CORE.fromSource, src_iris["uk_mot_lookup"]))

        for r in grp_rows:
            tid = r["test_item_id"].strip()
            pid = r["parent_id"].strip()
            if tid in mot_group_iris and pid in mot_group_iris and pid != tid:
                g_insp.add((mot_group_iris[tid], SKOS.broader, mot_group_iris[pid]))

        # SKOS & CandidateLink crosswalk for MOT top groups -> NHTSA Component
        for tid, entry in sorted(mot_map_by_id.items()):
            if tid not in mot_group_iris or entry["relation"] == "noMatch":
                continue
            gu = mot_group_iris[tid]
            skos_pred = SKOS.exactMatch if entry["relation"] == "exactMatch" else SKOS.closeMatch
            score = 0.90 if entry["relation"] == "exactMatch" else 0.75
            for head in entry["nhtsa_heads"]:
                ch = canon_head(head)
                if ch not in comp_iris:
                    continue
                cu = comp_iris[ch]
                g_insp.add((gu, skos_pred, cu))
                g_core.add((cu, skos_pred, gu))
                lid = f"cmot-{slug(ch)}-{tid}"
                add_candidate_link(
                    g_insp, lid, cu, gu,
                    "component_mot_group", score, review_overrides,
                    matched_head=ch, note=f"SKOS {entry['relation']}: {entry['mot_name']}",
                )
                cand_edges["component_mot_group"] += 1
                cand_pool["component_mot_group"].append({
                    "link_id": lid, "nhtsa_head": ch, "mot_item_id": tid,
                    "mot_name": entry["mot_name"], "relation": entry["relation"], "score": score,
                })

        # item_detail.csv (Class 4 RFR defects)
        det_rows = [
            r for r in csv.DictReader(io.StringIO(zf.read("item_detail.csv").decode("utf-8", errors="replace")), delimiter="|")
            if r.get("test_class_id") == "4"
        ]
        for r in det_rows:
            rfr_id = r["rfr_id"].strip()
            tid = r["test_item_id"].strip()
            if not rfr_id or tid not in mot_group_iris:
                continue
            u = mk_iri(INSP, "mot-defect", f"c4_rfr_{rfr_id}")
            mot_defect_iris[rfr_id] = u
            rdesc = clean_text(r.get("rfr_desc") or f"RFR {rfr_id}", 200)
            add_typed(g_insp, u, INSP.MotDefectItem, f"MOT RFR {rfr_id}: {rdesc[:100]}")
            add_lit(g_insp, u, INSP.rfrId, rfr_id)
            add_lit(g_insp, u, INSP.testClassId, "4")
            g_insp.add((u, INSP.inItemGroup, mot_group_iris[tid]))
            add_lit(g_insp, u, INSP.defaultSeverity, map_mot_severity(r.get("rfr_deficiency_category") or ""))
            add_lit(g_insp, u, INSP.minorItemFlag, (r.get("minor_item") or "").strip().upper() == "Y", XSD.boolean)
            add_lit(g_insp, u, CORE.description, rdesc)
            add_lit(g_insp, u, INSP.inspectionManualDesc, r.get("rfr_insp_manual_desc") or "")
            g_insp.add((u, CORE.fromSource, src_iris["uk_mot_lookup"]))

        # mdr_rfr_location.csv
        loc_count = 0
        for r in csv.DictReader(io.StringIO(zf.read("mdr_rfr_location.csv").decode("utf-8", errors="replace")), delimiter="|"):
            lid = r["id"].strip()
            if not lid:
                continue
            u = mk_iri(INSP, "mot-loc", lid)
            lbl = " / ".join(x for x in (r.get("lateral"), r.get("longitudinal"), r.get("vertical")) if x) or f"Location {lid}"
            add_typed(g_insp, u, INSP.MotLocation, lbl)
            add_lit(g_insp, u, INSP.locationId, lid)
            add_lit(g_insp, u, INSP.lateral, r.get("lateral") or "")
            add_lit(g_insp, u, INSP.longitudinal, r.get("longitudinal") or "")
            add_lit(g_insp, u, INSP.vertical, r.get("vertical") or "")
            g_insp.add((u, CORE.fromSource, src_iris["uk_mot_lookup"]))
            loc_count += 1

        # mdr_fuel_types.csv
        fuel_count = 0
        electrified_codes = {"EL", "HY", "ED", "FC", "GB", "GD", "PE"}
        for r in csv.DictReader(io.StringIO(zf.read("mdr_fuel_types.csv").decode("utf-8", errors="replace")), delimiter="|"):
            fc = r["type_code"].strip()
            fn = r["fuel_type"].strip()
            if not fc:
                continue
            u = mk_iri(INSP, "fuel", fc)
            add_typed(g_insp, u, INSP.FuelType, f"{fc}: {fn}")
            add_lit(g_insp, u, INSP.fuelCode, fc)
            add_lit(g_insp, u, INSP.fuelName, fn)
            add_lit(g_insp, u, INSP.isElectrified, fc in electrified_codes or "electric" in fn.lower() or "hybrid" in fn.lower(), XSD.boolean)
            g_insp.add((u, CORE.fromSource, src_iris["uk_mot_lookup"]))
            fuel_count += 1

    # Stream UK MOT 2023 aggregated cohort defect stats (NO vehicle_id, k<5 suppressed!)
    print("Streaming UK MOT 2023 test_result + test_item for Honda CR-V/Accord 2018...")
    mot_2023 = stream_mot_2023_honda_2018()
    stat_visible = 0
    stat_suppressed = 0
    stat_skipped_unknown_rfr = 0
    if mot_2023.get("available"):
        for (mg, rfr_id, sev, bucket), cnt in sorted(mot_2023["cell_counts"].items()):
            if rfr_id not in mot_defect_iris:
                stat_skipped_unknown_rfr += 1
                continue
            v_uri = veh_iris[("HONDA", mg, "2018")]
            cohort_n = mot_2023["cohort_tests"].get(mg, 0)
            su = mk_iri(INSP, "stat", f"HONDA_{mg}_2018__2023__rfr_{rfr_id}__{sev}__{bucket}")
            is_supp = cnt < 5
            add_typed(g_insp, su, INSP.InspectionDefectStat, f"MOT 2023 {mg} 2018 RFR {rfr_id} {sev} {bucket}")
            g_insp.add((su, INSP.forVehicle, v_uri))
            add_lit(g_insp, su, INSP.testYear, 2023, XSD.integer)
            g_insp.add((su, INSP.forDefectItem, mot_defect_iris[rfr_id]))
            add_lit(g_insp, su, INSP.observedSeverity, sev)
            add_lit(g_insp, su, INSP.mileageBucket, bucket)
            add_lit(g_insp, su, INSP.testsInCohort, cohort_n, XSD.integer)
            add_lit(g_insp, su, INSP.suppressed, is_supp, XSD.boolean)
            if not is_supp:
                add_lit(g_insp, su, INSP.defectCount, cnt, XSD.integer)
                stat_visible += 1
            else:
                stat_suppressed += 1
            g_insp.add((su, CORE.fromSource, src_iris["uk_mot_2023"]))

    # =========================================================================
    # 5. SIGNAL: COVESA VSS v6.1 + W3C VSSo + commaai/opendbc CAN DBC
    # =========================================================================
    vsso_classes = set(re.findall(r"vsso:([A-Za-z0-9_]+)\s+a\s+owl:Class", (EXT / "w3c_vsso" / "vss_rel_2.2.ttl").read_text(encoding="utf-8")))
    vss_prefixes = (
        "Vehicle.Powertrain.TractionBattery",
        "Vehicle.Powertrain.ElectricMotor",
        "Vehicle.Powertrain.CombustionEngine",
        "Vehicle.Powertrain.FuelSystem",
        "Vehicle.ADAS",
        "Vehicle.Diagnostics",
        "Vehicle.Chassis.Brake",
        "Vehicle.Chassis.ParkingBrake",
        "Vehicle.Chassis.SteeringWheel",
        "Vehicle.Chassis.Axle",
        "Vehicle.Body.Lights",
        "Vehicle.Cabin.Seat",
        "Vehicle.Speed",
        "Vehicle.TraveledDistance",
    )
    vss_branch_rules = sorted(vss_map_cfg["entries"], key=lambda e: -len(e["vss_prefix"]))
    vss_iris: dict[str, URIRef] = {}
    vsso_matched_count = 0

    with (EXT / "covesa_vss_v6.1.csv").open(encoding="utf-8", errors="replace") as fh:
        vss_rows_sel = [
            r for r in csv.DictReader(fh)
            if any(r["Signal"] == p or r["Signal"].startswith(p + ".") for p in vss_prefixes)
        ]

    for r in vss_rows_sel:
        sig = r["Signal"].strip()
        u = mk_iri(SIGNAL, "vss", sig)
        vss_iris[sig] = u
        ntype = (r.get("Type") or "branch").strip().lower()
        if ntype not in {"branch", "attribute", "sensor", "actuator"}:
            ntype = "branch"
        add_typed(g_signal, u, SIGNAL.VehicleSignal, sig)
        add_lit(g_signal, u, SIGNAL.vssPath, sig)
        add_lit(g_signal, u, SIGNAL.nodeType, ntype)
        add_lit(g_signal, u, SIGNAL.dataType, r.get("DataType") or "")
        add_lit(g_signal, u, CORE.unit, r.get("Unit") or "")
        add_lit(g_signal, u, CORE.description, r.get("Desc") or "")
        add_lit(g_signal, u, SIGNAL.vssVersion, "v6.1")
        mn, mx = safe_decimal_str(r.get("Min") or ""), safe_decimal_str(r.get("Max") or "")
        if mn is not None:
            add_lit(g_signal, u, CORE.minValue, mn, XSD.decimal)
        if mx is not None:
            add_lit(g_signal, u, CORE.maxValue, mx, XSD.decimal)
        g_signal.add((u, CORE.fromSource, src_iris["covesa_vss_61"]))

        # W3C VSSo closeMatch
        parts = sig.split(".")
        cands = [parts[-1], "".join(parts[-2:]), "".join(parts[1:])]
        hit = next((c for c in cands if c in vsso_classes), None)
        if hit:
            g_signal.add((u, SKOS.closeMatch, VSSO[hit]))
            vsso_matched_count += 1

        # Component mapping on exact branch roots
        for rule in vss_branch_rules:
            if sig == rule["vss_prefix"]:
                skos_pred = SKOS.exactMatch if rule["relation"] == "exactMatch" else SKOS.closeMatch
                for h in rule["nhtsa_heads"]:
                    ch = canon_head(h)
                    if ch in comp_iris:
                        g_signal.add((u, CORE.hasComponent, comp_iris[ch]))
                        g_signal.add((u, skos_pred, comp_iris[ch]))
                break

    for sig, u in vss_iris.items():
        if "." in sig:
            parent = sig.rsplit(".", 1)[0]
            if parent in vss_iris:
                g_signal.add((u, SKOS.broader, vss_iris[parent]))

    # commaai/opendbc CAN messages & signals
    dbc_curated = {(e["dbc_file"], e["message"]): e for e in dbc_map_cfg["entries"]}
    platform_by_file = {
        "_bosch_2018.dbc": "HONDA_2018_BOSCH",
        "_bosch_radar_acc.dbc": "HONDA_2018_BOSCH",
        "_honda_common.dbc": "HONDA_COMMON",
        "honda_crv_ex_2017_body.dbc": "HONDA_CRV_BODY",
        "honda_clarity_hybrid_2018_can.dbc": "HONDA_CLARITY_HYBRID_2018",
        "byd_atto3.dbc": "BYD_ATTO3",
        "tesla_model3_vehicle.dbc": "TESLA_MODEL3",
        "tesla_powertrain.dbc": "TESLA_MODEL3",
    }
    can_msg_count = 0
    can_sig_count = 0
    for dbc_path in sorted((EXT / "opendbc").glob("*.dbc")):
        fname = dbc_path.name
        platform = platform_by_file.get(fname, "UNKNOWN")
        for msg in parse_dbc_file(dbc_path):
            mu = mk_iri(SIGNAL, "can-msg", f"{dbc_path.stem}__{msg['name']}")
            add_typed(g_signal, mu, SIGNAL.CanMessage, f"{msg['name']} ({fname})")
            add_lit(g_signal, mu, SIGNAL.dbcFile, fname)
            add_lit(g_signal, mu, SIGNAL.vehiclePlatform, platform)
            add_lit(g_signal, mu, SIGNAL.frameId, msg["frame_id"], XSD.integer)
            add_lit(g_signal, mu, SIGNAL.messageName, msg["name"])
            add_lit(g_signal, mu, SIGNAL.byteLength, msg["byte_length"], XSD.integer)
            add_lit(g_signal, mu, SIGNAL.senderNode, msg["sender"])
            g_signal.add((mu, CORE.fromSource, src_iris["commaai_opendbc"]))
            can_msg_count += 1

            cur_e = dbc_curated.get((fname, msg["name"]))
            if cur_e:
                for vp in cur_e.get("vss_paths") or []:
                    if vp in vss_iris:
                        g_signal.add((mu, SIGNAL.mapsToVss, vss_iris[vp]))
                for h in cur_e.get("nhtsa_heads") or []:
                    ch = canon_head(h)
                    if ch in comp_iris:
                        g_signal.add((mu, CORE.hasComponent, comp_iris[ch]))
                        lid = f"ccan-{slug(ch)}-{dbc_path.stem}-{msg['name']}"
                        sc = float(cur_e["score"])
                        add_candidate_link(
                            g_signal, lid, comp_iris[ch], mu,
                            "component_can_message", sc, review_overrides,
                            matched_head=ch, note=cur_e.get("note") or f"{fname}:{msg['name']}",
                        )
                        cand_edges["component_can_message"] += 1
                        cand_pool["component_can_message"].append({
                            "link_id": lid, "nhtsa_head": ch, "dbc_file": fname,
                            "message": msg["name"], "platform": platform,
                            "vss_paths": cur_e.get("vss_paths") or [], "score": sc,
                            "note": cur_e.get("note") or "",
                        })

            for sg in msg["signals"]:
                su = mk_iri(SIGNAL, "can-sig", f"{dbc_path.stem}__{msg['name']}__{sg['name']}")
                add_typed(g_signal, su, SIGNAL.CanSignal, f"{msg['name']}.{sg['name']}")
                g_signal.add((su, SIGNAL.inMessage, mu))
                add_lit(g_signal, su, SIGNAL.signalName, sg["name"])
                add_lit(g_signal, su, SIGNAL.startBit, sg["start_bit"], XSD.integer)
                add_lit(g_signal, su, SIGNAL.bitLength, sg["bit_length"], XSD.integer)
                for p_uri, raw_v in (
                    (SIGNAL.scaleFactor, sg["factor"]),
                    (SIGNAL.scaleOffset, sg["offset"]),
                    (CORE.minValue, sg["min"]),
                    (CORE.maxValue, sg["max"]),
                ):
                    dv = safe_decimal_str(raw_v)
                    if dv is not None:
                        add_lit(g_signal, su, p_uri, dv, XSD.decimal)
                add_lit(g_signal, su, CORE.unit, sg["unit"])
                g_signal.add((su, CORE.fromSource, src_iris["commaai_opendbc"]))
                can_sig_count += 1

    # =========================================================================
    # 6. EV_BATTERY (Track 2): Figshare 30162841 Safe CSV + Academic Metadata
    # =========================================================================
    acad_meta = json.loads((EXT / "academic_metadata.json").read_text(encoding="utf-8"))
    ds_iris: dict[str, URIRef] = {}

    for f_entry in acad_meta.get("figshare", []):
        fid = str(f_entry["id"])
        du = mk_iri(EVB, "dataset", f"figshare_{fid}")
        ds_iris[f"figshare_{fid}"] = du
        add_typed(g_evb, du, EVB.BatteryDataset, f_entry["title"])
        add_lit(g_evb, du, EVB.doi, f_entry["doi"])
        add_lit(g_evb, du, CORE.description, f"Figshare CC-BY-4.0 dataset ({f_entry['total_bytes']} bytes)")
        add_lit(g_evb, du, RDFS.seeAlso, f_entry["url"], XSD.anyURI)
        add_lit(g_evb, du, EVB.dataFormat, "CSV labels + fold splits (safe CSV ingested)" if fid == "30162841" else "tar.gz metadata only")
        g_evb.add((du, CORE.fromSource, src_iris["figshare_30162841" if fid == "30162841" else "academic_datacite"]))

    for z_entry in acad_meta.get("datacite_zenodo", []):
        zid = z_entry["doi"].split("zenodo.")[-1]
        du = mk_iri(EVB, "dataset", f"zenodo_{zid}")
        ds_iris[f"zenodo_{zid}"] = du
        add_typed(g_evb, du, EVB.BatteryDataset, z_entry["title"])
        add_lit(g_evb, du, EVB.doi, z_entry["doi"])
        add_lit(g_evb, du, CORE.description, f"Zenodo DataCite metadata ({z_entry['publication_year']}, CC-BY-4.0; browser download only)")
        add_lit(g_evb, du, RDFS.seeAlso, z_entry["url"], XSD.anyURI)
        add_lit(g_evb, du, EVB.dataFormat, "DataCite metadata only (Zenodo WAF 403 for scripts)")
        g_evb.add((du, CORE.fromSource, src_iris["academic_datacite"]))

    # Ingest Figshare 30162841 safe CSV files (NEVER unpickle *.pkl!)
    evb_vss_targets = [
        "Vehicle.Powertrain.TractionBattery.StateOfCharge.Current",
        "Vehicle.Powertrain.TractionBattery.StateOfHealth",
        "Vehicle.Powertrain.TractionBattery.Temperature.Max",
        "Vehicle.Powertrain.TractionBattery.Temperature.Min",
        "Vehicle.Powertrain.TractionBattery.CellVoltage.Min",
        "Vehicle.Powertrain.TractionBattery.CellVoltage.Max",
        "Vehicle.Powertrain.TractionBattery.Charging.IsCharging",
        "Vehicle.TraveledDistance",
    ]
    evb_vss_iris = [vss_iris[p] for p in evb_vss_targets if p in vss_iris]

    fig_ds_uri = ds_iris["figshare_30162841"]
    ev_veh_agg: dict[tuple[str, str], dict] = {}
    ev_cohort_agg: dict[tuple[str, str, str], dict] = {}
    ev_total_snippets = 0

    with zipfile.ZipFile(EXT / "figshare_30162841" / "battery_dataset.zip") as zf:
        for brand in ("battery_brand1", "battery_brand2", "battery_brand3"):
            for sub in ("train_labels.csv", "test_labels.csv"):
                member = f"battery_dataset/{brand}/{sub}"
                if member not in zf.namelist():
                    continue
                with zf.open(member) as fh:
                    for r in csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8", errors="replace")):
                        car = r["car"].strip()
                        raw_lbl = r["label"].strip()
                        flbl = "fault_abnormal" if raw_lbl == "1" else "normal"
                        ev_total_snippets += 1
                        try:
                            mil = float(r["mileage"])
                        except Exception:
                            mil = None
                        try:
                            seg = int(float(r["charge_segment"]))
                        except Exception:
                            seg = 0

                        vk = (brand, car)
                        if vk not in ev_veh_agg:
                            ev_veh_agg[vk] = {"has_fault": False, "n": 0}
                        ev_veh_agg[vk]["n"] += 1
                        if flbl == "fault_abnormal":
                            ev_veh_agg[vk]["has_fault"] = True

                        ck = (brand, car, flbl)
                        if ck not in ev_cohort_agg:
                            ev_cohort_agg[ck] = {
                                "raw_lbl": raw_lbl, "n": 0, "seg_max": 0,
                                "mil_min": None, "mil_max": None, "mil_sum": 0.0, "mil_cnt": 0,
                            }
                        st = ev_cohort_agg[ck]
                        st["n"] += 1
                        if seg > st["seg_max"]:
                            st["seg_max"] = seg
                        if mil is not None:
                            if st["mil_min"] is None or mil < st["mil_min"]:
                                st["mil_min"] = mil
                            if st["mil_max"] is None or mil > st["mil_max"]:
                                st["mil_max"] = mil
                            st["mil_sum"] += mil
                            st["mil_cnt"] += 1

    add_lit(g_evb, fig_ds_uri, EVB.vehicleCount, len(ev_veh_agg), XSD.integer)
    add_lit(g_evb, fig_ds_uri, EVB.snippetCount, ev_total_snippets, XSD.integer)

    ev_veh_iris: dict[tuple[str, str], URIRef] = {}
    for (brand, car), vinfo in sorted(ev_veh_agg.items()):
        vu = mk_iri(EVB, "veh", f"fig30162841__{brand}__car_{car}")
        ev_veh_iris[(brand, car)] = vu
        add_typed(g_evb, vu, EVB.BatteryVehicleRef, f"EV {brand} car {car}")
        add_lit(g_evb, vu, EVB.datasetVehicleCode, f"{brand}_car_{car}")
        add_lit(g_evb, vu, EVB.brandCohort, brand)
        g_evb.add((vu, EVB.inDataset, fig_ds_uri))
        add_lit(g_evb, vu, EVB.vehicleFaultStatus, "fault_abnormal" if vinfo["has_fault"] else "normal")
        g_evb.add((vu, CORE.fromSource, src_iris["figshare_30162841"]))

    ev_summary_count = 0
    for (brand, car, flbl), st in sorted(ev_cohort_agg.items()):
        su = mk_iri(EVB, "snippet", f"fig30162841__{brand}__car_{car}__{flbl}")
        add_typed(g_evb, su, EVB.BatterySnippetSummary, f"{brand} car {car} ({flbl}, n={st['n']})")
        add_lit(g_evb, su, EVB.snippetId, f"{brand}_car_{car}_{flbl}")
        add_lit(g_evb, su, EVB.brandCohort, brand)
        g_evb.add((su, EVB.forBatteryVehicle, ev_veh_iris[(brand, car)]))
        add_lit(g_evb, su, EVB.faultLabel, flbl)
        add_lit(g_evb, su, EVB.rawLabelCode, st["raw_lbl"])
        add_lit(g_evb, su, EVB.sampleCount, st["n"], XSD.integer)
        add_lit(g_evb, su, EVB.chargeSegmentMax, st["seg_max"], XSD.integer)
        if st["mil_cnt"] > 0:
            add_lit(g_evb, su, EVB.mileageMinKm, f"{st['mil_min']:.2f}", XSD.decimal)
            add_lit(g_evb, su, EVB.mileageMaxKm, f"{st['mil_max']:.2f}", XSD.decimal)
            add_lit(g_evb, su, EVB.mileageMeanKm, f"{st['mil_sum'] / st['mil_cnt']:.2f}", XSD.decimal)
        for vsu in evb_vss_iris:
            g_evb.add((su, EVB.observesSignal, vsu))
        g_evb.add((su, CORE.fromSource, src_iris["figshare_30162841"]))
        ev_summary_count += 1

        # Create battery_fault_signal CandidateLinks for faulty cohort summaries to core TractionBattery signals
        if flbl == "fault_abnormal":
            for sig_path, sc, rsn in (
                ("Vehicle.Powertrain.TractionBattery.StateOfCharge.Current", 0.85, "Charging snippet battery SOC trajectory"),
                ("Vehicle.Powertrain.TractionBattery.CellVoltage.Min", 0.85, "Abnormal charging voltage drop / inconsistency indicator"),
                ("Vehicle.Powertrain.TractionBattery.Temperature.Max", 0.80, "Thermal anomaly indicator during charging"),
                ("Vehicle.Powertrain.TractionBattery.StateOfHealth", 0.75, "Long-term mileage-linked degradation proxy"),
            ):
                if sig_path in vss_iris:
                    lid = f"ebfs-{brand}-car{car}-{sig_path.split('.')[-1]}"
                    add_candidate_link(
                        g_evb, lid, su, vss_iris[sig_path],
                        "battery_fault_signal", sc, review_overrides, note=rsn,
                    )
                    cand_edges["battery_fault_signal"] += 1
                    cand_pool["battery_fault_signal"].append({
                        "link_id": lid, "brand": brand, "car": car, "snippets": st["n"],
                        "mileage_mean_km": round(st["mil_sum"] / st["mil_cnt"], 1) if st["mil_cnt"] else None,
                        "vss_path": sig_path, "score": sc, "note": rsn,
                    })

    # =========================================================================
    # 7. Serialize 6 modular TTLs + representative sample_abox.ttl for ROBOT HermiT
    # =========================================================================
    module_graphs = {
        "core": g_core,
        "recall": g_recall,
        "diagnostics": g_diag,
        "inspection": g_insp,
        "signal": g_signal,
        "ev_battery": g_evb,
    }
    module_stats = {}
    for mname, mg in module_graphs.items():
        out_p = OUT_RDF / f"{mname}.ttl"
        mg.serialize(destination=str(out_p), format="turtle")
        module_stats[mname] = {
            "file": f"rdf/v3/{mname}.ttl",
            "triples": len(mg),
            "bytes": out_p.stat().st_size,
        }
        print(f"Wrote {out_p} ({len(mg)} triples, {out_p.stat().st_size:,} bytes)")

    # Build a compact representative sample_abox.ttl spanning all 6 modules for ROBOT HermiT
    g_sample = new_graph()
    sample_subjects = [
        src_iris["nhtsa_cmpl"], src_iris["tc_vrdb"], src_iris["wal33d_dtc"],
        src_iris["uk_mot_2023"], src_iris["covesa_vss_61"], src_iris["figshare_30162841"],
        veh_iris[("HONDA", "CR-V", "2018")], veh_iris[("HONDA", "ACCORD", "2018")],
        comp_iris["FUEL SYSTEM"], comp_iris["FORWARD COLLISION AVOIDANCE"], comp_iris["STEERING"],
        comp_iris_by_odino.get("11407338") or next(iter(comp_iris_by_odino.values())),
        us_recall_iris["20V314000"], ca_recall_meta["2020236"]["uri"],
        dtc_iris["P0300"], dtc_iris["P1326"],
        pid_iris["01-0C"],
        mot_group_iris["5430"], mot_group_iris["5730"],
        vss_iris["Vehicle.Powertrain.TractionBattery.StateOfCharge.Current"],
        fig_ds_uri,
    ]
    # Add one DtcDefinition, one InspectionDefectStat, one CanMessage, one BatterySnippetSummary, one CandidateLink
    for dinfo in defs_by_code.get("P1326", [])[:1]:
        sample_subjects.append(dinfo["uri"])
    for s in list(g_insp.subjects(RDF.type, INSP.InspectionDefectStat))[:2]:
        sample_subjects.append(s)
        for o in g_insp.objects(s, INSP.forDefectItem):
            sample_subjects.append(o)
            for g_o in g_insp.objects(o, INSP.inItemGroup):
                sample_subjects.append(g_o)
    for s in list(g_signal.subjects(RDF.type, SIGNAL.CanMessage))[:2]:
        sample_subjects.append(s)
    for s in list(g_evb.subjects(RDF.type, EVB.BatterySnippetSummary))[:2]:
        sample_subjects.append(s)
        for v_o in g_evb.objects(s, EVB.forBatteryVehicle):
            sample_subjects.append(v_o)
    for s in list(g_recall.subjects(RDF.type, CORE.CandidateLink))[:2]:
        sample_subjects.append(s)

    subj_set = set(sample_subjects)
    for mg in module_graphs.values():
        for s in subj_set:
            for t in mg.triples((s, None, None)):
                g_sample.add(t)
    sample_path = OUT_RDF / "sample_abox.ttl"
    g_sample.serialize(destination=str(sample_path), format="turtle")
    print(f"Wrote {sample_path} ({len(g_sample)} triples for ROBOT HermiT check)")

    # Save candidate pool snapshot to review/ for structured human review sampling
    (REV_DIR / "v3_candidate_pool.json").write_text(
        json.dumps({k: v for k, v in cand_pool.items()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Aggregate final graph stats
    def count_cls(g: Graph, cls: URIRef) -> int:
        return len(set(g.subjects(RDF.type, cls)))

    nodes_summary = {
        "DataSource": count_cls(g_core, CORE.DataSource),
        "VehicleModelYear": count_cls(g_core, CORE.VehicleModelYear),
        "Component": count_cls(g_core, CORE.Component),
        "Complaint": count_cls(g_core, CORE.Complaint),
        "Investigation": count_cls(g_core, CORE.Investigation),
        "QaThread": count_cls(g_core, CORE.QaThread),
        "JurisdictionRecall_US": len(us_recall_iris),
        "JurisdictionRecall_CA": len(ca_recall_meta),
        "DTC": len(dtc_iris),
        "DtcDefinition": def_count,
        "RepairStep": step_count,
        "Part_MechanicDB": len(part_iris) - rcl_part_count,
        "Part_RecallOEM": rcl_part_count,
        "ObdPid": len(pid_iris),
        "MotItemGroup": len(mot_group_iris),
        "MotDefectItem": len(mot_defect_iris),
        "MotLocation": loc_count,
        "FuelType": fuel_count,
        "InspectionDefectStat_Visible": stat_visible,
        "InspectionDefectStat_Suppressed": stat_suppressed,
        "VehicleSignal_VSS": len(vss_iris),
        "VehicleSignal_VSSoMatched": vsso_matched_count,
        "CanMessage": can_msg_count,
        "CanSignal": can_sig_count,
        "BatteryDataset": len(ds_iris),
        "BatteryVehicleRef": len(ev_veh_iris),
        "BatterySnippetSummary": ev_summary_count,
        "CandidateLink_Total": sum(count_cls(mg, CORE.CandidateLink) for mg in module_graphs.values()),
    }
    hard_total = sum(hard_edges.values())
    cand_total = sum(cand_edges.values())

    stats_out = {
        "measured_at": "2026-11-25 Asia/Shanghai",
        "elapsed_seconds": round(time.time() - t_start, 2),
        "modules": module_stats,
        "total_abox_triples": sum(m["triples"] for m in module_stats.values()),
        "nodes": nodes_summary,
        "hard_edges": {**dict(hard_edges), "hard_total": hard_total},
        "candidate_edges": {**dict(cand_edges), "candidate_total": cand_total},
        "ratios": {
            "hard_over_candidate": round(hard_total / cand_total, 4) if cand_total else None,
            "hard_share_of_all_edges": round(hard_total / (hard_total + cand_total), 4) if (hard_total + cand_total) else None,
            "candidate_share_of_all_edges": round(cand_total / (hard_total + cand_total), 4) if (hard_total + cand_total) else None,
        },
        "cross_jurisdiction_full_corpus_reference": tc_full_corpus_stats,
        "cross_jurisdiction_honda2018_slice": {
            "us_recalls": len(us_recall_iris),
            "ca_recalls": len(ca_recall_meta),
            "hard_key_matches_xjur_mfr_token": xjur_hard,
            "candidate_matches_xjur_mmy_system_window": cand_edges["xjur_mmy_system_window"],
        },
        "mot_2023_streaming_stats": {
            k: v for k, v in mot_2023.items() if k not in ("cell_counts", "cell_counts_str")
        } | {
            "total_unique_cells": len(mot_2023.get("cell_counts", {})),
            "visible_cells_ge_5": stat_visible,
            "suppressed_cells_lt_5": stat_suppressed,
            "skipped_unknown_rfr": stat_skipped_unknown_rfr,
        },
        "ev_battery_30162841_stats": {
            "total_csv_snippets_aggregated": ev_total_snippets,
            "vehicles_total": len(ev_veh_agg),
            "vehicles_with_fault": sum(1 for v in ev_veh_agg.values() if v["has_fault"]),
            "cohort_summary_nodes": ev_summary_count,
            "raw_waveforms_note": "Figshare 30162841 safe CSVs contain car, label, mileage, and charge_segment; raw cell voltage/temperature waveforms in Figshare 23659323 are pickled (.pkl) files and were intentionally not unpickled for security.",
        },
    }
    stats_path = STATS_DIR / "v3-graph-stats.json"
    stats_path.write_text(json.dumps(stats_out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {stats_path} in {stats_out['elapsed_seconds']}s")
    print("Total ABox triples:", stats_out["total_abox_triples"])
    print("Hard edges:", stats_out["hard_edges"])
    print("Candidate edges:", stats_out["candidate_edges"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
