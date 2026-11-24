#!/usr/bin/env python3
"""纠正召回平面文件的字段偏移（0 起第 23–26 列为部件标识/名称/描述/零件号），并尝试与通告对齐。

从 data/raw/FLAT_RCL_POST_2010.zip 读取，结果写入 data/step2/（不进 git）。
"""
from __future__ import annotations

import json, re, zipfile, io
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RCL_ZIP = REPO_ROOT / "data" / "raw" / "FLAT_RCL_POST_2010.zip"
OUT = REPO_ROOT / "data" / "step2"
OUT.mkdir(parents=True, exist_ok=True)
YEAR = "2018"
CORE = {"CR-V", "ACCORD"}
HONDA_PART = re.compile(r"\b(\d{5}-[A-Z0-9]{3}-[A-Z0-9]{3})\b", re.I)
SB_TOKEN = re.compile(r"\b(?:TSB|SB|SERVICE\s+BULLETIN(?:\s+NUMBER)?|BULLETIN)\s*[:#]?\s*([A-Z]?\d{2}[-–]\d{3}[A-Z]?)\b", re.I)
CAMPNO_TOKEN = re.compile(r"\b(\d{2}V-?\d{3}(?:\d{3})?)\b", re.I)


def norm_space(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().upper())


def alnum(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", norm_space(s))


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
    return "ACCORD" if m == "ACCORD HYBRID" else m


def desc_matches_row_model(desc: str, model: str) -> bool:
    d = alnum(desc)
    m = alnum(model)
    if not d:
        return False
    if m == "ACCORD":
        return d.startswith("ACCORD")
    if m == "CRV":
        return d.startswith("CRV")
    return m in d or d in m


rows = []
with zipfile.ZipFile(RCL_ZIP) as z:
    name = z.namelist()[0]
    with z.open(name) as fh:
        wrap = io.TextIOWrapper(fh, encoding="latin-1", newline="")
        for line in wrap:
            p = line.rstrip("\n\r").split("\t")
            if len(p) < 27:
                continue
            if norm_space(p[2]) not in {"HONDA", "HONDA MOTOR"}:
                continue
            model = norm_model(p[3])
            year = (p[4] or "").strip()
            if year != YEAR or model_group(model) not in CORE:
                continue
            notes = p[22] if len(p) > 22 else ""
            defect = p[19] if len(p) > 19 else ""
            remedy = p[21] if len(p) > 21 else ""
            blob = " ".join([notes or "", defect or "", remedy or ""])
            name_ = (p[24] or "").strip()
            desc = (p[25] or "").strip()
            ptno_raw = (p[26] or "").strip()
            ptnos = sorted({x.upper() for x in HONDA_PART.findall(ptno_raw)})
            rec = {
                "record_id": (p[0] or "").strip(),
                "campno": (p[1] or "").strip(),
                "make": "HONDA",
                "model": model,
                "model_group": model_group(model),
                "year": year,
                "mfr_campno": (p[5] or "").strip(),
                "comp_desc": norm_space(p[6]),
                "rcl_cmpt_id": (p[23] or "").strip() if len(p) > 23 else "",
                "mfr_comp_name": name_,
                "mfr_comp_desc": desc,
                "mfr_comp_ptno_raw": ptno_raw,
                "mfr_comp_ptnos": ptnos,
                "part_desc_matches_row_model": desc_matches_row_model(desc, model),
                "do_not_drive": (p[27] or "").strip() if len(p) > 27 else "",
                "park_outside": (p[28] or "").strip() if len(p) > 28 else "",
                "bulletins_from_official_text": sorted({m.upper() for m in SB_TOKEN.findall(blob)}),
                "campno_from_official_text": sorted({alnum(x).ljust(10,"0")[:10] if False else (
                    (lambda t: t+"000" if re.fullmatch(r"\d{2}V\d{3}", t) else t)(alnum(x))
                ) for x in CAMPNO_TOKEN.findall(blob)}),
                "parts_from_official_text": sorted({x.upper() for x in HONDA_PART.findall(blob)}),
            }
            rows.append(rec)

# campaign rollup
camps = defaultdict(lambda: {
    "campno": "", "models": set(), "mfr_tokens": set(), "comp_paths": set(),
    "rcl_cmpt_ids": set(), "mfr_comp_names": set(),
    "ptnos_all": set(), "ptnos_model_matched": set(), "ptno_rows_all": 0,
    "ptno_rows_model_matched": 0, "part_applications": [],
    "bulletins": set(), "parts_from_text": set(), "rows": 0,
    "n_mfr_campno": 0, "n_ptno_field": 0, "n_name_field": 0, "n_cmpt_id": 0,
})
for r in rows:
    c = camps[r["campno"]]
    c["campno"] = r["campno"]
    c["models"].add(r["model"])
    for t in re.split(r"[,;/]| AND ", r["mfr_campno"] or ""):
        t = norm_space(t)
        if t:
            c["mfr_tokens"].add(t)
    if r["mfr_campno"]:
        c["n_mfr_campno"] += 1
    if r["comp_desc"]:
        c["comp_paths"].add(r["comp_desc"])
    if r["rcl_cmpt_id"]:
        c["rcl_cmpt_ids"].add(r["rcl_cmpt_id"]); c["n_cmpt_id"] += 1
    if r["mfr_comp_name"]:
        c["mfr_comp_names"].add(r["mfr_comp_name"]); c["n_name_field"] += 1
    if r["mfr_comp_ptnos"]:
        c["n_ptno_field"] += 1
        c["ptnos_all"].update(r["mfr_comp_ptnos"])
        c["ptno_rows_all"] += 1
        app = {
            "mfr_comp_name": r["mfr_comp_name"],
            "mfr_comp_desc": r["mfr_comp_desc"],
            "ptnos": r["mfr_comp_ptnos"],
            "row_model": r["model"],
            "matches_row_model": r["part_desc_matches_row_model"],
        }
        if app not in c["part_applications"]:
            c["part_applications"].append(app)
        if r["part_desc_matches_row_model"]:
            c["ptnos_model_matched"].update(r["mfr_comp_ptnos"])
            c["ptno_rows_model_matched"] += 1
    c["bulletins"].update(r["bulletins_from_official_text"])
    c["parts_from_text"].update(r["parts_from_official_text"])
    c["rows"] += 1

# TSB re-join: part numbers in TSB summaries / document ids vs bulletins
tsb = json.loads((OUT / "tsb_communications.json").read_text())["items"]
all_ptnos = set()
all_bulletins = set()
ptno_to_camp = defaultdict(set)
for camp, c in camps.items():
    all_ptnos |= c["ptnos_all"]
    all_bulletins |= c["bulletins"]
    for p in c["ptnos_all"] | c["parts_from_text"]:
        ptno_to_camp[p].add(camp)

tsb_part_hits = []
tsb_bulletin_hits = []
for comm in tsb:
    text_ids = " ".join([
        comm.get("tsb_document_id") or "",
        comm.get("replacement_sb") or "",
        " ".join(comm.get("parts_from_summary") or []),
        " ".join(comm.get("bulletins_from_summary") or []),
    ]).upper()
    # also check stored summary-mined parts
    for p in (comm.get("parts_from_summary") or []):
        if p in ptno_to_camp:
            for camp in ptno_to_camp[p]:
                tsb_part_hits.append((comm["nhtsa_id"], comm["tsb_document_id"], camp, p))
    # document id vs bulletin
    doc = norm_space(comm.get("tsb_document_id") or "")
    m = re.search(r"(A?\d{2}-\d{3}[A-Z]?)$", doc)
    bare = m.group(1) if m else ""
    for b in all_bulletins:
        if doc == b or bare == b or doc.endswith(b) or (bare and alnum(bare) == alnum(b)):
            # need camp for bulletin
            for camp, c in camps.items():
                if b in c["bulletins"]:
                    tsb_bulletin_hits.append((comm["nhtsa_id"], doc, camp, b))

# hard recall -> OEM part edges (campaign-level distinct PTNO)
hard_parts = []
for camp, c in camps.items():
    for p in sorted(c["ptnos_all"]):
        hard_parts.append({
            "campno": camp,
            "part_number": p,
            "model_matched": p in c["ptnos_model_matched"],
            "relation": "recall_has_manufacturer_part_number",
        })

# serialize camps
camp_table = []
for camp in sorted(camps):
    c = camps[camp]
    camp_table.append({
        "campno": camp,
        "models": sorted(c["models"]),
        "mfr_tokens": sorted(c["mfr_tokens"]),
        "n_rows": c["rows"],
        "n_comp_paths": len(c["comp_paths"]),
        "comp_paths": sorted(c["comp_paths"]),
        "n_rcl_cmpt_ids": len(c["rcl_cmpt_ids"]),
        "n_mfr_comp_names": len(c["mfr_comp_names"]),
        "mfr_comp_names": sorted(c["mfr_comp_names"]),
        "n_distinct_ptnos_all": len(c["ptnos_all"]),
        "ptnos_all": sorted(c["ptnos_all"]),
        "n_distinct_ptnos_model_matched": len(c["ptnos_model_matched"]),
        "ptnos_model_matched": sorted(c["ptnos_model_matched"]),
        "ptno_rows_all": c["ptno_rows_all"],
        "ptno_rows_model_matched": c["ptno_rows_model_matched"],
        "n_rows_with_mfr_campno": c["n_mfr_campno"],
        "n_rows_with_ptno": c["n_ptno_field"],
        "n_rows_with_mfr_comp_name": c["n_name_field"],
        "bulletins_from_official_text": sorted(c["bulletins"]),
        "parts_from_official_text": sorted(c["parts_from_text"]),
        "n_part_applications": len(c["part_applications"]),
    })

# update public_hard_keys
hk = json.loads((OUT / "public_hard_keys.json").read_text())
hk["rcl_honda_2018_corrected"] = {
    "note": "Corrected 0-based offsets: [23]=RCL_CMPT_ID, [24]=MFR_COMP_NAME, [25]=MFR_COMP_DESC (often the model the part applies to), [26]=MFR_COMP_PTNO, [27]=DO_NOT_DRIVE, [28]=PARK_OUTSIDE. Earlier occupancy treating [27] as PTNO was wrong (that field is Yes/No).",
    "coverage_rows": len(rows),
    "distinct_campno": len(camps),
    "n_rows_with_real_ptno": sum(1 for r in rows if r["mfr_comp_ptnos"]),
    "n_distinct_ptnos": len(all_ptnos),
    "n_distinct_ptnos_model_matched": len({p for c in camps.values() for p in c["ptnos_model_matched"]}),
    "occupancy_rate_mfr_campno": round(sum(1 for r in rows if r["mfr_campno"]) / max(len(rows), 1), 4),
    "occupancy_rate_real_ptno": round(sum(1 for r in rows if r["mfr_comp_ptnos"]) / max(len(rows), 1), 4),
    "occupancy_rate_mfr_comp_name": round(sum(1 for r in rows if r["mfr_comp_name"]) / max(len(rows), 1), 4),
    "occupancy_rate_rcl_cmpt_id": round(sum(1 for r in rows if r["rcl_cmpt_id"]) / max(len(rows), 1), 4),
    "n_campaigns_with_ptno": sum(1 for c in camps.values() if c["ptnos_all"]),
    "n_campaigns_with_mfr_token": sum(1 for c in camps.values() if any(t not in {"MULTIPLE CODES", "REFER TO COMMENTS"} for t in c["mfr_tokens"])),
    "bulletins_mined_from_official_text_all": sorted(all_bulletins),
    "campaigns": camp_table,
}
hk["hard_links_tsb_to_recall"] = {
    "n_links": 0,
    "n_unique_nhtsa_id_campno": 0,
    "n_communications_linked": 0,
    "n_campaigns_linked": 0,
    "campaigns_linked": [],
    "methods": {},
    "links": [],
    "tsb_part_hits_after_correction": tsb_part_hits,
    "tsb_bulletin_hits_after_correction": tsb_bulletin_hits,
    "note": "No systematic TSB↔recall identifier equality in the flat files for this slice. TSB 'Mfr Internal Campaign ID' and manufacturer component fields are empty. TSB document IDs (e.g. A20-036) do not match the one bulletin number found via a separately searched PDF (20-039 for 20V771, and A20-039 is not in the TSB file). Official FLAT_RCL NOTES/defect/remedy also yielded no bulletin tokens under a 'Service Bulletin' label pattern.",
}
hk["hard_links_recall_to_oem_part"] = {
    "n_unique_campno_part": len(hard_parts),
    "n_unique_parts": len(all_ptnos),
    "n_model_matched_pairs": sum(1 for x in hard_parts if x["model_matched"]),
    "links": hard_parts,
    "note": "Structured MFR_COMP_PTNO values after correcting field offsets. One campaign row may list a part that applies to a different model (MFR_COMP_DESC). model_matched=true when the description matches the row model (Accord/CR-V).",
}
(OUT / "public_hard_keys.json").write_text(json.dumps(hk, ensure_ascii=False, indent=2))
(OUT / "rcl_parts_honda_2018_corrected.json").write_text(json.dumps({
    "n": len(rows),
    # do not store official long text; structural only, and drop raw long if any
    "rows": [{k: v for k, v in r.items() if k not in {"notes", "defect", "remedy"}} for r in rows],
}, ensure_ascii=False, indent=2))

print("rows", len(rows), "camps", len(camps))
print("distinct ptnos", len(all_ptnos), "model-matched", len({p for c in camps.values() for p in c["ptnos_model_matched"]}))
print("hard camp-part", len(hard_parts), "model-matched pairs", sum(1 for x in hard_parts if x["model_matched"]))
print("bulletins from text", sorted(all_bulletins))
print("tsb part hits", tsb_part_hits)
print("tsb bulletin hits", tsb_bulletin_hits)
for c in camp_table:
    print(c["campno"], "mfr", c["mfr_tokens"], "ptnos_all", c["n_distinct_ptnos_all"], "matched", c["n_distinct_ptnos_model_matched"], "names", c["mfr_comp_names"], "bulletins", c["bulletins_from_official_text"])
print("DONE")
