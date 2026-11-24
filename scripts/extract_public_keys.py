#!/usr/bin/env python3
"""从公开召回与厂商通信中抽出本田 CR-V / 雅阁 2018 的硬键字段。

不写入车辆识别号、投诉叙述原文，也不把通告或召回长文本写入输出。
只保留结构标识、部件路径和占用率计数。
数据从 data/raw/ 读取，结果写到 data/step2/（均不进 git）。
"""
from __future__ import annotations

import json
import re
import zipfile
import io
from collections import Counter, defaultdict
from pathlib import Path

# 路径相对于仓库根目录。请先运行 scripts/download_public_data.py --fetch-large
REPO_ROOT = Path(__file__).resolve().parents[1]
RAW = REPO_ROOT / "data" / "raw"
OUT = REPO_ROOT / "data" / "step2"
OUT.mkdir(parents=True, exist_ok=True)
SLICE = REPO_ROOT / "data" / "honda-2018" / "slice_nhtsa_qa.json"
RCL_ZIP = RAW / "FLAT_RCL_POST_2010.zip"
TSBS_ZIPS = [
    RAW / "TSBS_RECEIVED_2015-2019.zip",
    RAW / "TSBS_RECEIVED_2020-2024.zip",
    RAW / "TSBS_RECEIVED_2025-2026.zip",
]

YEAR = "2018"
MAKES_OK = {"HONDA"}
MODELS_CORE = {"CR-V", "ACCORD"}

CAMPNO_TOKEN = re.compile(r"\b(\d{2}V-?\d{3}(?:\d{3})?)\b", re.I)
HONDA_PART = re.compile(r"\b(\d{5}-[A-Z0-9]{3}-[A-Z0-9]{3})\b", re.I)
SB_TOKEN = re.compile(r"\b(?:TSB|SB|SERVICE\s+BULLETIN(?:\s+NUMBER)?|BULLETIN)\s*[:#]?\s*([A-Z]?\d{2}[-–]\d{3}[A-Z]?)\b", re.I)
SB_BARE = re.compile(r"\b(\d{2}-\d{3}[A-Z]?)\b")
# Honda campaign tokens often like K2G, V2F, X95, A20, P5C
MFR_CAMP_TOKEN = re.compile(r"\b([A-Z]\d{2}|[A-Z]\d[A-Z]|[A-Z]{2}\d)\b")


def norm_space(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().upper())


def alnum(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", norm_space(s))


def norm_make(s: str) -> str:
    m = norm_space(s)
    return {"HONDA MOTOR": "HONDA"}.get(m, m)


def norm_model(s: str) -> str:
    m = norm_space(s)
    loose = alnum(m)
    if loose in {"CRV", "HONDACRV"}:
        return "CR-V"
    if loose == "ACCORD":
        return "ACCORD"
    if loose in {"ACCORDHYBRID", "ACCORDHEV"}:
        return "ACCORD HYBRID"
    return m


def model_group(s: str) -> str:
    m = norm_model(s)
    if m == "ACCORD HYBRID":
        return "ACCORD"
    return m


def iter_zip_tabular(zip_path: Path):
    with zipfile.ZipFile(zip_path) as z:
        name = z.namelist()[0]
        with z.open(name) as fh:
            wrap = io.TextIOWrapper(fh, encoding="latin-1", newline="")
            for line in wrap:
                yield line.rstrip("\n\r").split("\t")


def tokens_from_mfr_camp(s: str) -> list[str]:
    out = []
    for raw in re.split(r"[,;/]| AND ", s or ""):
        t = norm_space(raw)
        t = t.strip(" .")
        if not t:
            continue
        if t not in out:
            out.append(t)
    return out


def normalize_campno(s: str) -> str:
    t = alnum(s)
    # 20V771 -> 20V771000 if 7 chars ending mid
    if re.fullmatch(r"\d{2}V\d{3}", t):
        t = t + "000"
    return t


# ---------- recalls: part / manufacturer campaign fields ----------
rcl_rows = []
rcl_occ = Counter()
n_rcl_scanned_honda2018 = 0
bulletin_hits = Counter()
campno_in_text = Counter()
honda_part_in_text = Counter()

CAMPS_TARGET = set()  # fill from slice too

slice_data = json.loads(SLICE.read_text())
slice_camps = sorted({r["campno"] for r in slice_data["recalls"]})
slice_mfr = {}
for r in slice_data["recalls"]:
    slice_mfr.setdefault(r["campno"], set()).update(tokens_from_mfr_camp(r.get("mfr_campno") or ""))

for p in iter_zip_tabular(RCL_ZIP):
    if len(p) < 7:
        continue
    make = norm_make(p[2])
    model = norm_model(p[3])
    year = (p[4] or "").strip()
    if make not in MAKES_OK or model_group(model) not in MODELS_CORE or year != YEAR:
        continue
    n_rcl_scanned_honda2018 += 1
    campno = (p[1] or "").strip()
    mfr_campno = (p[5] or "").strip() if len(p) > 5 else ""
    comp = norm_space(p[6]) if len(p) > 6 else ""
    rcl_cmpt_id = (p[24] or "").strip() if len(p) > 24 else ""
    mfr_comp_name = (p[25] or "").strip() if len(p) > 25 else ""
    mfr_comp_desc = (p[26] or "").strip() if len(p) > 26 else ""
    mfr_comp_ptno = (p[27] or "").strip() if len(p) > 27 else ""
    # occupancy on official long fields without storing them
    notes = p[23] if len(p) > 23 else ""
    defect = p[19] if len(p) > 19 else ""
    remedy = p[21] if len(p) > 21 else ""
    blob = " ".join([notes or "", defect or "", remedy or ""])
    sbs = set(m.upper() for m in SB_TOKEN.findall(blob))
    # bare 20-039 only if preceded nearby by bulletin words — already in SB_TOKEN
    camps_in = {normalize_campno(x) for x in CAMPNO_TOKEN.findall(blob)}
    parts_in = {x.upper() for x in HONDA_PART.findall(blob)}
    for x in sbs:
        bulletin_hits[x] += 1
    for x in camps_in:
        campno_in_text[x] += 1
    for x in parts_in:
        honda_part_in_text[x] += 1
    rec = {
        "record_id": (p[0] or "").strip(),
        "campno": campno,
        "make": make,
        "model": model,
        "model_group": model_group(model),
        "year": year,
        "mfr_campno": mfr_campno,
        "mfr_campno_tokens": tokens_from_mfr_camp(mfr_campno),
        "comp_desc": comp,
        "rcl_cmpt_id": rcl_cmpt_id,
        "mfr_comp_name": mfr_comp_name,
        "mfr_comp_desc": mfr_comp_desc,
        "mfr_comp_ptno": mfr_comp_ptno,
        "n_fields": len(p),
        "bulletins_from_official_text": sorted(sbs),
        "campno_tokens_from_official_text": sorted(camps_in),
        "honda_part_tokens_from_official_text": sorted(parts_in),
        "has_notes": bool((notes or "").strip()),
        "has_defect": bool((defect or "").strip()),
        "has_remedy": bool((remedy or "").strip()),
    }
    for k in [
        "mfr_campno",
        "rcl_cmpt_id",
        "mfr_comp_name",
        "mfr_comp_desc",
        "mfr_comp_ptno",
        "bulletins_from_official_text",
        "honda_part_tokens_from_official_text",
    ]:
        if rec[k]:
            rcl_occ[k] += 1
    rcl_rows.append(rec)

# ---------- TSBS stream ----------
tsb_rows = []
tsb_occ = Counter()
tsb_types = Counter()
n_tsb_lines = 0
n_tsb_honda = 0
n_tsb_honda_2018_core = 0
unique_ids = set()
unique_tsb_docs = set()

for zp in TSBS_ZIPS:
    for p in iter_zip_tabular(zp):
        n_tsb_lines += 1
        if len(p) < 11:
            continue
        make = norm_make(p[7])
        if make not in MAKES_OK:
            continue
        n_tsb_honda += 1
        model = norm_model(p[8])
        year = (p[9] or "").strip()
        if year != YEAR or model_group(model) not in MODELS_CORE:
            continue
        n_tsb_honda_2018_core += 1
        nhtsa_id = (p[0] or "").strip()
        repl = (p[1] or "").strip()
        date_added = (p[2] or "").strip()
        tsb_id = (p[3] or "").strip()
        mfr_date = (p[4] or "").strip()
        mfr_camp = (p[5] or "").strip()
        comm_type = (p[6] or "").strip()
        comps = (p[10] or "").strip()
        mfr_sys = (p[11] or "").strip() if len(p) > 11 else ""
        mfr_sub = (p[12] or "").strip() if len(p) > 12 else ""
        summary = p[13] if len(p) > 13 else ""
        # only mine identifiers from summary; do not keep text
        sbs = set(m.upper() for m in SB_TOKEN.findall(summary or ""))
        camps_in = {normalize_campno(x) for x in CAMPNO_TOKEN.findall(summary or "")}
        parts_in = {x.upper() for x in HONDA_PART.findall(summary or "")}
        rec = {
            "nhtsa_id": nhtsa_id,
            "replacement_sb": repl,
            "date_added": date_added,
            "tsb_document_id": tsb_id,
            "mfr_date": mfr_date,
            "mfr_internal_campaign_or_sw": mfr_camp,
            "mfr_camp_tokens": tokens_from_mfr_camp(mfr_camp),
            "communication_type": comm_type,
            "make": make,
            "model": model,
            "model_group": model_group(model),
            "year": year,
            "nhtsa_components": norm_space(comps),
            "nhtsa_component_list": [norm_space(x) for x in comps.split(",") if norm_space(x)],
            "mfr_component_system": norm_space(mfr_sys),
            "mfr_component_subsystem": norm_space(mfr_sub),
            "campno_tokens_from_summary": sorted(camps_in),
            "bulletin_tokens_from_summary": sorted(sbs),
            "honda_part_tokens_from_summary": sorted(parts_in),
            "summary_len": len(summary or ""),
        }
        for k in [
            "nhtsa_id",
            "replacement_sb",
            "tsb_document_id",
            "mfr_internal_campaign_or_sw",
            "communication_type",
            "nhtsa_components",
            "mfr_component_system",
            "mfr_component_subsystem",
            "campno_tokens_from_summary",
            "honda_part_tokens_from_summary",
        ]:
            if rec[k]:
                tsb_occ[k] += 1
        tsb_types[comm_type or "(empty)"] += 1
        unique_ids.add(nhtsa_id)
        unique_tsb_docs.add(tsb_id)
        tsb_rows.append(rec)

# ---------- joins ----------
# Unique communications (nhtsa_id + tsb_document_id + campaign field)
comms = {}
for r in tsb_rows:
    key = (r["nhtsa_id"], r["tsb_document_id"])
    comms.setdefault(key, {
        "nhtsa_id": r["nhtsa_id"],
        "tsb_document_id": r["tsb_document_id"],
        "replacement_sb": r["replacement_sb"],
        "communication_type": r["communication_type"],
        "mfr_internal_campaign_or_sw": r["mfr_internal_campaign_or_sw"],
        "mfr_camp_tokens": list(r["mfr_camp_tokens"]),
        "models": set(),
        "component_paths": set(),
        "mfr_systems": set(),
        "mfr_subsystems": set(),
        "campno_from_summary": set(),
        "parts_from_summary": set(),
        "bulletins_from_summary": set(),
        "row_count": 0,
    })
    c = comms[key]
    c["row_count"] += 1
    c["models"].add(r["model"])
    c["component_paths"].update(r["nhtsa_component_list"] or ([r["nhtsa_components"]] if r["nhtsa_components"] else []))
    if r["mfr_component_system"]:
        c["mfr_systems"].add(r["mfr_component_system"])
    if r["mfr_component_subsystem"]:
        c["mfr_subsystems"].add(r["mfr_component_subsystem"])
    c["campno_from_summary"].update(r["campno_tokens_from_summary"])
    c["parts_from_summary"].update(r["honda_part_tokens_from_summary"])
    c["bulletins_from_summary"].update(r["bulletin_tokens_from_summary"])

recalls_by_camp = defaultdict(lambda: {
    "campno": "",
    "models": set(),
    "mfr_tokens": set(),
    "comp_paths": set(),
    "rcl_cmpt_ids": set(),
    "mfr_comp_names": set(),
    "mfr_comp_ptnos": set(),
    "bulletins_from_text": set(),
    "parts_from_text": set(),
    "rows": 0,
})
for r in rcl_rows:
    c = recalls_by_camp[r["campno"]]
    c["campno"] = r["campno"]
    c["models"].add(r["model"])
    c["mfr_tokens"].update(r["mfr_campno_tokens"])
    if r["comp_desc"]:
        c["comp_paths"].add(r["comp_desc"])
    if r["rcl_cmpt_id"]:
        c["rcl_cmpt_ids"].add(r["rcl_cmpt_id"])
    if r["mfr_comp_name"]:
        c["mfr_comp_names"].add(r["mfr_comp_name"])
    if r["mfr_comp_ptno"]:
        c["mfr_comp_ptnos"].add(r["mfr_comp_ptno"])
    c["bulletins_from_text"].update(r["bulletins_from_official_text"])
    c["parts_from_text"].update(r["honda_part_tokens_from_official_text"])
    c["rows"] += 1

# Build lookup indexes
mfr_token_to_camps = defaultdict(set)
campno_index = {}
ptno_to_camps = defaultdict(set)
bulletin_to_camps = defaultdict(set)
for camp, rec in recalls_by_camp.items():
    campno_index[normalize_campno(camp)] = camp
    for t in rec["mfr_tokens"]:
        mfr_token_to_camps[t].add(camp)
    for ptn in rec["mfr_comp_ptnos"] | rec["parts_from_text"]:
        ptno_to_camps[ptn].add(camp)
    for b in rec["bulletins_from_text"]:
        bulletin_to_camps[b].add(camp)

hard_tsb_recall = []  # list of dicts
methods = Counter()

def add_link(comm, camp, method, evidence):
    hard_tsb_recall.append({
        "nhtsa_id": comm["nhtsa_id"],
        "tsb_document_id": comm["tsb_document_id"],
        "communication_type": comm["communication_type"],
        "campno": camp,
        "method": method,
        "evidence": evidence,
        "models": sorted(comm["models"]),
    })
    methods[method] += 1

seen_pair = set()
for comm in comms.values():
    hits = defaultdict(set)  # camp -> methods
    # 1. Mfr Internal Campaign ID exact token vs recall MFGCAMPNO tokens
    for t in comm["mfr_camp_tokens"]:
        # skip things that look like software versions (pure numeric / dotted)
        if re.fullmatch(r"[\d.]+", t):
            continue
        if t in mfr_token_to_camps:
            for camp in mfr_token_to_camps[t]:
                hits[camp].add(("mfr_campaign_token_exact", t))
        # also 20V771000 form stored in that field
        nc = normalize_campno(t)
        if nc in campno_index:
            hits[campno_index[nc]].add(("mfr_field_equals_campno", t))
    # 2. CAMPNO mentioned in TSB summary
    for nc in comm["campno_from_summary"]:
        if nc in campno_index:
            hits[campno_index[nc]].add(("campno_in_tsb_summary", nc))
    # 3. TSB document id vs bulletin tokens mined from official recall text
    doc = norm_space(comm["tsb_document_id"])
    doc_alnum = alnum(doc)
    for b, camps in bulletin_to_camps.items():
        if doc == b or alnum(b) == doc_alnum or doc.endswith(b) or b.endswith(doc):
            for camp in camps:
                hits[camp].add(("tsb_document_id_equals_bulletin_in_recall_text", f"{doc}~{b}"))
    # also try last token of TSB id (e.g. A20-039 vs 20-039)
    m = re.search(r"(\d{2}-\d{3}[A-Z]?)$", doc)
    if m:
        bare = m.group(1)
        if bare in bulletin_to_camps:
            for camp in bulletin_to_camps[bare]:
                hits[camp].add(("tsb_document_id_suffix_equals_bulletin", bare))
    # 4. Honda part number overlap (TSB summary vs RCL structured PTNO or recall text)
    for ptn in comm["parts_from_summary"]:
        if ptn in ptno_to_camps:
            for camp in ptno_to_camps[ptn]:
                hits[camp].add(("honda_part_number_overlap", ptn))
    for camp, evs in hits.items():
        key = (comm["nhtsa_id"], comm["tsb_document_id"], camp)
        if key in seen_pair:
            continue
        seen_pair.add(key)
        # prefer strongest method
        order = [
            "mfr_campaign_token_exact",
            "mfr_field_equals_campno",
            "tsb_document_id_equals_bulletin_in_recall_text",
            "tsb_document_id_suffix_equals_bulletin",
            "honda_part_number_overlap",
            "campno_in_tsb_summary",
        ]
        evs_sorted = sorted(evs, key=lambda x: order.index(x[0]) if x[0] in order else 99)
        method, evidence = evs_sorted[0]
        add_link(comm, camp, method, evidence)

# unique hard edges at communication-campaign level
unique_hard = {(x["nhtsa_id"], x["campno"]) for x in hard_tsb_recall}
unique_tsb_linked = {x["nhtsa_id"] for x in hard_tsb_recall}
unique_camps_linked = {x["campno"] for x in hard_tsb_recall}

# TSB component paths that exactly equal a recall component path (not a hard ID, but official vocab overlap)
exact_comp_pairs = 0
tsb_comp_recall_comp = []
for comm in comms.values():
    for camp, rec in recalls_by_camp.items():
        shared = comm["component_paths"] & rec["comp_paths"]
        if shared:
            exact_comp_pairs += 1
            tsb_comp_recall_comp.append({
                "nhtsa_id": comm["nhtsa_id"],
                "tsb_document_id": comm["tsb_document_id"],
                "campno": camp,
                "shared_paths": sorted(shared),
                "also_hard_id": (comm["nhtsa_id"], camp) in unique_hard,
            })

# serialize sets
def ser_comm(c):
    return {
        "nhtsa_id": c["nhtsa_id"],
        "tsb_document_id": c["tsb_document_id"],
        "replacement_sb": c["replacement_sb"],
        "communication_type": c["communication_type"],
        "mfr_internal_campaign_or_sw": c["mfr_internal_campaign_or_sw"],
        "mfr_camp_tokens": c["mfr_camp_tokens"],
        "models": sorted(c["models"]),
        "component_paths": sorted(c["component_paths"]),
        "mfr_systems": sorted(c["mfr_systems"]),
        "mfr_subsystems": sorted(c["mfr_subsystems"]),
        "campno_from_summary": sorted(c["campno_from_summary"]),
        "parts_from_summary": sorted(c["parts_from_summary"]),
        "bulletins_from_summary": sorted(c["bulletins_from_summary"]),
        "row_count": c["row_count"],
    }

def ser_rcl(c):
    return {
        "campno": c["campno"],
        "models": sorted(c["models"]),
        "mfr_tokens": sorted(c["mfr_tokens"]),
        "comp_paths": sorted(c["comp_paths"]),
        "rcl_cmpt_ids": sorted(c["rcl_cmpt_ids"]),
        "mfr_comp_names": sorted(c["mfr_comp_names"]),
        "mfr_comp_ptnos": sorted(c["mfr_comp_ptnos"]),
        "bulletins_from_text": sorted(c["bulletins_from_text"]),
        "parts_from_text": sorted(c["parts_from_text"]),
        "rows": c["rows"],
    }

# occupancy by campaign
camp_table = []
for camp in sorted(recalls_by_camp):
    rec = recalls_by_camp[camp]
    camp_table.append({
        "campno": camp,
        "models": sorted(rec["models"]),
        "mfr_tokens": sorted(rec["mfr_tokens"]),
        "n_comp_paths": len(rec["comp_paths"]),
        "n_rcl_cmpt_ids": len(rec["rcl_cmpt_ids"]),
        "n_mfr_comp_names": len(rec["mfr_comp_names"]),
        "n_mfr_comp_ptnos": len(rec["mfr_comp_ptnos"]),
        "mfr_comp_ptnos": sorted(rec["mfr_comp_ptnos"]),
        "mfr_comp_names": sorted(rec["mfr_comp_names"]),
        "bulletins_from_official_text": sorted(rec["bulletins_from_text"]),
        "hard_linked_tsb_ids": sorted({x["nhtsa_id"] for x in hard_tsb_recall if x["campno"] == camp}),
        "hard_linked_tsb_docs": sorted({x["tsb_document_id"] for x in hard_tsb_recall if x["campno"] == camp}),
    })

summary = {
    "slice": "HONDA CR-V + ACCORD 2018 (ACCORD HYBRID counted under ACCORD group for TSB/RCL extra rows)",
    "sources": {
        "tsbs_txt_dictionary": "https://static.nhtsa.gov/odi/ffdd/tsbs/TSBS.txt",
        "tsbs_zips": [str(p) for p in TSBS_ZIPS],
        "rcl_zip": str(RCL_ZIP),
        "api_recalls_by_vehicle": "https://api.nhtsa.gov/recalls/recallsByVehicle",
        "api_complaints_by_vehicle": "https://api.nhtsa.gov/complaints/complaintsByVehicle",
        "api_recalls_by_campaign": "https://api.nhtsa.gov/recalls/campaignNumber",
        "recall_pdf_pattern": "https://static.nhtsa.gov/odi/rcl/{year}/{PREFIX}-{campYYVxxx}-{suffix}.pdf (suffix not derivable; directories do not list files)",
    },
    "tsb": {
        "lines_scanned_all_makes": n_tsb_lines,
        "honda_rows_any_year": n_tsb_honda,
        "honda_2018_core_model_rows": n_tsb_honda_2018_core,
        "unique_nhtsa_ids": len(unique_ids),
        "unique_tsb_document_ids": len(unique_tsb_docs),
        "row_occupancy": dict(tsb_occ),
        "communication_types": dict(tsb_types),
        "occupancy_rate_mfr_campaign_field": round(tsb_occ["mfr_internal_campaign_or_sw"] / max(n_tsb_honda_2018_core, 1), 4),
        "occupancy_rate_mfr_comp_system": round(tsb_occ["mfr_component_system"] / max(n_tsb_honda_2018_core, 1), 4),
        "occupancy_rate_part_in_summary": round(tsb_occ["honda_part_tokens_from_summary"] / max(n_tsb_honda_2018_core, 1), 4),
        "occupancy_rate_campno_in_summary": round(tsb_occ["campno_tokens_from_summary"] / max(n_tsb_honda_2018_core, 1), 4),
    },
    "rcl_honda_2018": {
        "coverage_rows": n_rcl_scanned_honda2018,
        "distinct_campno": len(recalls_by_camp),
        "row_occupancy": dict(rcl_occ),
        "occupancy_rate_mfr_campno": round(rcl_occ["mfr_campno"] / max(n_rcl_scanned_honda2018, 1), 4),
        "occupancy_rate_mfr_comp_ptno": round(rcl_occ["mfr_comp_ptno"] / max(n_rcl_scanned_honda2018, 1), 4),
        "occupancy_rate_rcl_cmpt_id": round(rcl_occ["rcl_cmpt_id"] / max(n_rcl_scanned_honda2018, 1), 4),
        "occupancy_rate_mfr_comp_name": round(rcl_occ["mfr_comp_name"] / max(n_rcl_scanned_honda2018, 1), 4),
        "campaigns": camp_table,
    },
    "hard_links_tsb_to_recall": {
        "n_links": len(hard_tsb_recall),
        "n_unique_nhtsa_id_campno": len(unique_hard),
        "n_communications_linked": len(unique_tsb_linked),
        "n_campaigns_linked": len(unique_camps_linked),
        "campaigns_linked": sorted(unique_camps_linked),
        "methods": dict(methods),
        "links": hard_tsb_recall,
        "note": "Hard means official identifier equality (manufacturer campaign token, NHTSA campaign number, TSB/document ID vs bulletin number mined from official recall text, or Honda 5-3-3 part number). Component-path overlap is reported separately and is not treated as a hard key.",
    },
    "component_path_exact_overlap_tsb_recall": {
        "n_comm_campaign_pairs_with_shared_full_path": len(tsb_comp_recall_comp),
        "n_also_hard_id": sum(1 for x in tsb_comp_recall_comp if x["also_hard_id"]),
        "pairs": tsb_comp_recall_comp,
    },
    "api_notes": {
        "recallsByVehicle_adds_part_or_bulletin_fields": False,
        "recallsByVehicle_keys": [
            "Component", "Consequence", "Make", "Manufacturer", "Model", "ModelYear",
            "NHTSACampaignNumber", "Notes", "Remedy", "ReportReceivedDate", "Summary",
            "overTheAirUpdate", "parkIt", "parkOutSide",
        ],
        "complaintsByVehicle_has_odiNumber_and_components": True,
        "complaintsByVehicle_has_campaign_or_tsb_or_part": False,
        "complaintsByVehicle_has_vin_and_summary": True,
        "tsb_api_by_vehicle": "https://api.nhtsa.gov/tsbs/tsbsByVehicle returned 403; no public TSB API used",
        "pdf_index": "odi/rcl/{year}/ and odi/tsbs/ return empty directory listings; PDF suffix is not a function of campaign number, so documents are not a systematic structured source",
    },
}

(OUT / "tsb_honda_2018_rows.json").write_text(
    json.dumps({"n": len(tsb_rows), "rows": tsb_rows}, ensure_ascii=False, indent=2)
)
(OUT / "rcl_parts_honda_2018.json").write_text(
    json.dumps({"n": len(rcl_rows), "rows": rcl_rows}, ensure_ascii=False, indent=2)
)
(OUT / "tsb_communications.json").write_text(
    json.dumps({"n": len(comms), "items": [ser_comm(c) for c in comms.values()]}, ensure_ascii=False, indent=2)
)
(OUT / "public_hard_keys.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))

print("TSB rows", n_tsb_honda_2018_core, "unique nhtsa_id", len(unique_ids), "unique docs", len(unique_tsb_docs))
print("TSB occupancy", dict(tsb_occ))
print("TSB types", dict(tsb_types))
print("RCL rows", n_rcl_scanned_honda2018, "camps", len(recalls_by_camp), "occ", dict(rcl_occ))
print("HARD links", len(hard_tsb_recall), "unique pairs", len(unique_hard), "methods", dict(methods))
print("campaigns", json.dumps(camp_table, ensure_ascii=False, indent=2))
print("DONE")
