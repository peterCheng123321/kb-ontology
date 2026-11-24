#!/usr/bin/env python3
"""统一部件路径，并按细粒度路径重算投诉与召回、调查之间的候选关联。

不写入车辆识别号，不写入投诉叙述原文。召回缺陷摘要只使用公开切片里已有的短摘录。
切片从 data/honda-2018/ 读取，结果写入 data/step2/（不进 git）。
"""
from __future__ import annotations

import json
import re
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SLICE = REPO_ROOT / "data" / "honda-2018" / "slice_nhtsa_qa.json"
MECH = REPO_ROOT / "data" / "honda-2018" / "mechanicdb.json"
STATS_OLD = REPO_ROOT / "data" / "honda-2018" / "stats.json"
REVIEW_OLD = REPO_ROOT / "review" / "review_10.json"
OUT = REPO_ROOT / "data" / "step2"
REVIEW_OUT = REPO_ROOT / "review"
OUT.mkdir(parents=True, exist_ok=True)
REVIEW_OUT.mkdir(parents=True, exist_ok=True)

# Official-ish L1 aliases. Keep NHTSA wording where possible; only merge known synonyms.
L1_ALIAS = {
    "FUEL/PROPULSION SYSTEM": "FUEL SYSTEM",
    "FUEL SYSTEM, GASOLINE": "FUEL SYSTEM",
    "FUEL SYSTEM, DIESEL": "FUEL SYSTEM",
    "FUEL SYSTEM, OTHER": "FUEL SYSTEM",
    "FUEL SYSTEM, GASOLINE": "FUEL SYSTEM",
    "ENGINE": "ENGINE AND ENGINE COOLING",
    "SERVICE BRAKES, HYDRAULIC": "SERVICE BRAKES",
    "SERVICE BRAKES, ELECTRIC": "SERVICE BRAKES",
    "SERVICE BRAKES, AIR": "SERVICE BRAKES",
    "POWERTRAIN": "POWER TRAIN",
    "POWER TRAIN": "POWER TRAIN",
    "VISIBILITY/WIPER": "VISIBILITY",
    "LATCHES/LOCKS/LINKAGES": "LATCHES/LOCKS/LINKAGES",
    "ELECTRICAL SYSTEM": "ELECTRICAL SYSTEM",
    "HYBRID PROPULSION SYSTEM": "HYBRID PROPULSION SYSTEM",
}

# SAE J2012 / OBD-II publicly known system groups (first 3 chars of P-codes).
# This is the commonly published grouping, not a copy of the SAE standard text.
DTC_GROUP = {
    "P00": ("Fuel and air metering and auxiliary emission controls", ["FUEL SYSTEM", "ENGINE AND ENGINE COOLING:ENGINE"]),
    "P01": ("Fuel and air metering", ["FUEL SYSTEM", "ENGINE AND ENGINE COOLING:ENGINE"]),
    "P02": ("Fuel and air metering (injector circuit)", ["FUEL SYSTEM", "ENGINE AND ENGINE COOLING:ENGINE"]),
    "P03": ("Ignition system or misfire", ["ENGINE AND ENGINE COOLING:ENGINE"]),
    "P04": ("Auxiliary emission controls", ["ENGINE AND ENGINE COOLING", "FUEL SYSTEM"]),
    "P05": ("Vehicle speed, idle control, and auxiliary inputs", ["VEHICLE SPEED CONTROL", "ENGINE AND ENGINE COOLING"]),
    "P06": ("Computer and output circuit", ["ELECTRICAL SYSTEM"]),
    "P07": ("Transmission", ["POWER TRAIN"]),
    "P08": ("Transmission", ["POWER TRAIN"]),
    "P09": ("Transmission", ["POWER TRAIN"]),
    "P0A": ("Hybrid propulsion", ["HYBRID PROPULSION SYSTEM", "ELECTRICAL SYSTEM"]),
    "P0B": ("Hybrid battery", ["HYBRID PROPULSION SYSTEM", "ELECTRICAL SYSTEM"]),
    "P0C": ("Hybrid / electric drivetrain", ["HYBRID PROPULSION SYSTEM", "ELECTRICAL SYSTEM"]),
}

DTC_LETTER = {
    "P": "Powertrain",
    "C": "Chassis",
    "B": "Body",
    "U": "Network / communications",
}

# Keyword → canonical NHTSA-style path (used for MechanicDB names and vehicle_qa Chinese terms).
# Longer / more specific patterns should be applied first.
KEYWORD_PATHS = [
    (r"fuel\s*pump|燃油泵|油泵", "FUEL SYSTEM:DELIVERY:FUEL PUMP"),
    (r"injector|喷油", "FUEL SYSTEM:DELIVERY:FUEL INJECTOR"),
    (r"evap|碳罐|燃油蒸发", "FUEL SYSTEM:DELIVERY:HOSES, LINES/PIPING, AND FITTINGS"),
    (r"oxygen\s*sensor|o2\s*sensor|氧传感器", "ENGINE AND ENGINE COOLING:EXHAUST SYSTEM"),
    (r"catalytic|三元|催化", "ENGINE AND ENGINE COOLING:EXHAUST SYSTEM"),
    (r"misfire|失火|点火线圈|ignition\s*coil", "ENGINE AND ENGINE COOLING:ENGINE"),
    (r"turbo|涡轮", "ENGINE AND ENGINE COOLING:ENGINE"),
    (r"coolant|thermostat|水箱|冷却液|节温器", "ENGINE AND ENGINE COOLING:COOLING SYSTEM"),
    (r"engine\s*oil|机油", "ENGINE AND ENGINE COOLING:ENGINE"),
    (r"\bengine\b|发动机", "ENGINE AND ENGINE COOLING:ENGINE"),
    (r"transmission|变速箱|变速器|变速", "POWER TRAIN"),
    (r"wheel\s*speed\s*sensor|轮速", "SERVICE BRAKES:ANTILOCK/TRACTION CONTROL/ELECTRONIC LIMITED SLIP"),
    (r"abs|制动防抱死", "SERVICE BRAKES:ANTILOCK/TRACTION CONTROL/ELECTRONIC LIMITED SLIP"),
    (r"brake\s*pedal|刹车踏板", "SERVICE BRAKES"),
    (r"brake|刹车|制动", "SERVICE BRAKES"),
    (r"power\s*steer|电动助力|转向机|转向齿", "STEERING:ELECTRIC POWER ASSIST SYSTEM"),
    (r"\bsteering\b|转向", "STEERING"),
    (r"occupant's?\s*classif|weight\s*sensor|座椅重量|乘员分类", "AIR BAGS:SENSOR:OCCUPANT CLASSIFICATION:FRONT PASSENGER"),
    (r"air\s*bag|气囊|SRS", "AIR BAGS"),
    (r"seat\s*belt|安全带|buckle|锁扣", "SEAT BELTS:FRONT:BUCKLE ASSEMBLY"),
    (r"rearview|backup\s*camera|倒车影像|后视摄像头", "BACK OVER PREVENTION:SENSING SYSTEM:CAMERA"),
    (r"body\s*control|BCM|车身控制", "ELECTRICAL SYSTEM:BODY CONTROL MODULE"),
    (r"windshield\s*wiper|雨刷|雨刮", "VISIBILITY:WINDSHIELD WIPER/WASHER"),
    (r"defrost|除雾|除霜", "VISIBILITY:DEFROSTER/DEFOGGER/HVAC SYSTEM"),
    (r"power\s*window|电动窗", "VISIBILITY:POWER WINDOW DEVICES AND CONTROLS"),
    (r"\bwiper\b", "VISIBILITY"),
    (r"exterior\s*light|转向灯|大灯|尾灯", "EXTERIOR LIGHTING"),
    (r"battery|电池", "ELECTRICAL SYSTEM:ALTERNATOR/GENERATOR/REGULATOR"),
    (r"can\s*bus|通信中断|network", "ELECTRICAL SYSTEM"),
    (r"electrical|电气|电路", "ELECTRICAL SYSTEM"),
    (r"suspension|悬挂|减震", "SUSPENSION"),
    (r"forward\s*collision|自动紧急制动|AEB|碰撞预警", "FORWARD COLLISION AVOIDANCE"),
    (r"lane\s*depart|车道偏离", "LANE DEPARTURE"),
    (r"vehicle\s*speed|车速", "VEHICLE SPEED CONTROL"),
]


def norm_space(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().upper())


def alias_l1(l1: str) -> str:
    l1 = norm_space(l1)
    if l1 in L1_ALIAS:
        return L1_ALIAS[l1]
    # "FUEL SYSTEM, GASOLINE" already covered; generic "X, Y" keep if not aliased
    return l1


def parse_path(raw: str) -> list[str]:
    s = norm_space(raw)
    if not s:
        return []
    # NHTSA uses colon as the hierarchy separator.
    parts = [norm_space(p) for p in s.split(":") if norm_space(p)]
    if not parts:
        return []
    parts[0] = alias_l1(parts[0])
    # After aliasing VISIBILITY/WIPER -> VISIBILITY, if original had no deeper levels,
    # path is just [VISIBILITY]. That is intentional (L1 only).
    # Drop duplicate adjacent
    out = []
    for p in parts:
        if not out or out[-1] != p:
            out.append(p)
    return out


def path_str(parts: list[str]) -> str:
    return ":".join(parts)


def depth(parts: list[str]) -> int:
    return len(parts)


def is_prefix(a: list[str], b: list[str]) -> bool:
    if len(a) > len(b):
        a, b = b, a
    return b[: len(a)] == a


def fine_match(a: list[str], b: list[str], raw_a: str = "", raw_b: str = "") -> dict | None:
    ra, rb = norm_space(raw_a), norm_space(raw_b)
    if ra and rb and ra == rb:
        # official labels identical, even if a single-level path
        parts = a or b or parse_path(ra)
        return {"kind": "exact_raw", "shared_depth": max(len(parts), 1), "shared": ra, "score": 0.95}
    if not a or not b:
        return None
    if a == b and len(a) >= 2:
        return {"kind": "exact_canonical_depth_ge2", "shared_depth": len(a), "shared": path_str(a), "score": 0.9}
    if is_prefix(a, b):
        shared = min(len(a), len(b))
        if shared >= 2:
            return {
                "kind": "prefix_depth_ge2",
                "shared_depth": shared,
                "shared": path_str(a if len(a) <= len(b) else b),
                "score": 0.8,
            }
        return None  # parent/child only at L1 — not fine
    if len(a) >= 2 and len(b) >= 2 and a[0] == b[0] and a[1] == b[1]:
        i = 0
        while i < len(a) and i < len(b) and a[i] == b[i]:
            i += 1
        if i >= 2:
            return {"kind": "common_prefix_ge2", "shared_depth": i, "shared": path_str(a[:i]), "score": 0.75}
    return None


def coarse_l1(a: list[str], b: list[str]) -> bool:
    return bool(a and b and a[0] == b[0])


def dtc_group(code: str) -> dict:
    c = (code or "").upper()
    letter = c[:1]
    family = DTC_LETTER.get(letter, "Unknown")
    paths = []
    group_name = family
    if letter == "P" and len(c) >= 3:
        key = c[:3]
        if key in DTC_GROUP:
            group_name, paths = DTC_GROUP[key][0], list(DTC_GROUP[key][1])
        else:
            # P1xxx+ manufacturer powertrain
            group_name, paths = "Manufacturer powertrain", ["ENGINE AND ENGINE COOLING", "POWER TRAIN"]
    elif letter == "C":
        paths = ["SERVICE BRAKES", "STEERING", "SUSPENSION", "ELECTRONIC STABILITY CONTROL (ESC)"]
    elif letter == "B":
        paths = ["AIR BAGS", "SEAT BELTS", "ELECTRICAL SYSTEM", "STRUCTURE"]
    elif letter == "U":
        paths = ["ELECTRICAL SYSTEM"]
    return {"code": c, "letter": letter, "group": group_name, "paths": [parse_path(p) for p in paths]}


def keyword_paths(text: str) -> list[list[str]]:
    t = text or ""
    hits = []
    seen = set()
    for pat, path in KEYWORD_PATHS:
        if re.search(pat, t, re.I):
            parts = parse_path(path)
            key = path_str(parts)
            if key not in seen:
                seen.add(key)
                hits.append(parts)
    return hits


def unique_paths(rows, field="comp_desc") -> list[str]:
    return sorted({norm_space(r.get(field) or "") for r in rows if r.get(field)})


def main():
    slice_data = json.loads(SLICE.read_text())
    mech = json.loads(MECH.read_text())
    old_stats = json.loads(STATS_OLD.read_text())
    old_review = json.loads(REVIEW_OLD.read_text())

    complaints = slice_data["complaints"]
    recalls = slice_data["recalls"]
    investigations = slice_data["investigations"]
    qa = slice_data["qa"]

    # Collect taxonomy from official NHTSA paths (full COMPDESC).
    raw_paths = []
    for src, rows in [("complaint", complaints), ("recall", recalls), ("investigation", investigations)]:
        for r in rows:
            raw = norm_space(r.get("comp_desc") or "")
            parts = parse_path(raw)
            raw_paths.append({"source": src, "raw": raw, "canonical": path_str(parts), "depth": depth(parts), "l1": parts[0] if parts else ""})

    tax_counter = Counter((x["canonical"], x["depth"], x["l1"]) for x in raw_paths)
    depth_hist = Counter(x["depth"] for x in raw_paths)
    l1_hist = Counter(x["l1"] for x in raw_paths)

    # Index complaints / recalls / inv by model, paths
    def index_by_odino(rows):
        m = defaultdict(lambda: {"model": "", "odino": "", "raw": set(), "paths": []})
        for r in rows:
            o = r["odino"]
            rec = m[o]
            rec["model"] = r["model"]
            rec["odino"] = o
            rec["year"] = r["year"]
            rec["make"] = r["make"]
            rec["dtcs"] = sorted(set(rec.get("dtcs") or []) | set(r.get("dtcs") or []))
            raw = norm_space(r.get("comp_desc") or "")
            if raw:
                rec["raw"].add(raw)
            parts = parse_path(raw)
            if raw and (raw, parts) not in rec["paths"]:
                rec["paths"].append((raw, parts))
        return m

    def index_by_camp(rows, id_field, id_name="id"):
        m = defaultdict(lambda: {"id": "", "models": set(), "raw": set(), "paths": [], "defect_summary": "", "subject": ""})
        for r in rows:
            k = r[id_field]
            rec = m[k]
            rec["id"] = k
            rec["models"].add(r["model"])
            raw = norm_space(r.get("comp_desc") or "")
            if raw:
                rec["raw"].add(raw)
            parts = parse_path(raw)
            if raw and (raw, parts) not in rec["paths"]:
                rec["paths"].append((raw, parts))
            if r.get("defect_summary") and not rec["defect_summary"]:
                rec["defect_summary"] = r["defect_summary"]
            if r.get("subject") and not rec["subject"]:
                rec["subject"] = r["subject"]
            rec["campno"] = r.get("campno") or ""
        return m

    cmp_idx = index_by_odino(complaints)
    rcl_idx = index_by_camp(recalls, "campno")
    inv_idx = index_by_camp(investigations, "action_number")

    def generate(cmp_idx, tgt_idx, require_model=True):
        fine, coarse_only = [], []
        for odino, c in cmp_idx.items():
            for tid, t in tgt_idx.items():
                if require_model and c["model"] not in t["models"]:
                    continue
                best_fine = None
                any_l1 = False
                evidence = []
                for raw_c, cp in c["paths"]:
                    for raw_t, tp in t["paths"]:
                        if coarse_l1(cp, tp) or (norm_space(raw_c) and alias_l1(norm_space(raw_c).split(":")[0]) == alias_l1(norm_space(raw_t).split(":")[0] if raw_t else "")):
                            any_l1 = True
                        fm = fine_match(cp, tp, raw_c, raw_t)
                        if fm:
                            evidence.append({
                                "complaint_path": raw_c or path_str(cp),
                                "target_path": raw_t or path_str(tp),
                                **fm,
                            })
                            if best_fine is None or fm["score"] > best_fine["score"]:
                                best_fine = fm
                if best_fine:
                    fine.append({
                        "odino": odino,
                        "model": c["model"],
                        "target_id": tid,
                        "kind": best_fine["kind"],
                        "score": best_fine["score"],
                        "shared_depth": best_fine["shared_depth"],
                        "shared": best_fine["shared"],
                        "complaint_paths": [raw or path_str(p) for raw, p in c["paths"]],
                        "target_paths": [raw or path_str(p) for raw, p in t["paths"]],
                        "n_evidence": len(evidence),
                    })
                elif any_l1:
                    coarse_only.append({
                        "odino": odino,
                        "model": c["model"],
                        "target_id": tid,
                        "kind": "l1_only",
                        "score": 0.6,
                        "shared_depth": 1,
                        "complaint_paths": [raw or path_str(p) for raw, p in c["paths"]],
                        "target_paths": [raw or path_str(p) for raw, p in t["paths"]],
                    })
        return fine, coarse_only

    fine_rcl, coarse_rcl = generate(cmp_idx, rcl_idx)
    fine_inv, coarse_inv = generate(cmp_idx, inv_idx)

    old_rcl = old_stats["candidate_edges"]["complaint_to_recall_mmy_component"]
    old_inv = old_stats["candidate_edges"]["complaint_to_investigation_mmy_component"]
    old_hard = old_stats["hard_edges"]["hard_total"]
    old_cand = old_stats["candidate_edges"]["candidate_total"]

    # Recompute other candidate types unchanged (qa lexicon + dtc cooccur) from old stats
    old_qa = old_stats["candidate_edges"]["qa_to_component_lexicon"]
    old_dtc = old_stats["candidate_edges"]["complaint_to_dtc_regex_cooccur"]

    new_cand_core = len(fine_rcl) + len(fine_inv)
    # Full candidate total if we replace only the two MMY+component families
    new_cand_total_replace = new_cand_core + old_qa + old_dtc
    old_core = old_rcl + old_inv

    # Load public hard keys if present
    hard_path = OUT / "public_hard_keys.json"
    new_hard_tsb = 0
    hard_tsb_links = []
    if hard_path.exists():
        hk = json.loads(hard_path.read_text())
        hard_tsb_links = hk.get("hard_links_tsb_to_recall", {}).get("links") or []
        new_hard_tsb = hk.get("hard_links_tsb_to_recall", {}).get("n_unique_nhtsa_id_campno") or len(
            {(x["nhtsa_id"], x["campno"]) for x in hard_tsb_links}
        )

    new_hard_total = old_hard + new_hard_tsb
    ratio_old = old_stats["ratios"]["hard_over_candidate"]
    ratio_new = new_hard_total / new_cand_total_replace if new_cand_total_replace else None

    # Previous 10-review survival under the new rule
    survival = []
    for item in old_review["items"]:
        odino, camp = item["odino"], item["campno"]
        kept = next((x for x in fine_rcl if x["odino"] == odino and x["target_id"] == camp), None)
        coarse = next((x for x in coarse_rcl if x["odino"] == odino and x["target_id"] == camp), None)
        survival.append({
            "odino": odino,
            "campno": camp,
            "old_judgment": item["judgment"],
            "old_method": item["method"],
            "old_complaint_components": item.get("complaint_component_values"),
            "old_recall_components": item.get("recall_component_values"),
            "survives_fine": bool(kept),
            "fine_kind": kept["kind"] if kept else None,
            "falls_to_l1_only": bool(coarse) and not kept,
        })

    # MechanicDB part names / DTC short names → paths
    mech_map = []
    for p in mech.get("parts") or []:
        name = p.get("part_name") or ""
        paths = keyword_paths(name)
        mech_map.append({
            "kind": "part",
            "id": p.get("part_id"),
            "name": name,
            "mapped_paths": [path_str(x) for x in paths],
            "mapped": bool(paths),
        })
    dtc_map = []
    for d in mech.get("dtc_codes") or []:
        code = d.get("dtc_code") or ""
        grp = dtc_group(code)
        text = " ".join([d.get("short_description") or "", d.get("fault_family") or "", d.get("system_category") or ""])
        kw = keyword_paths(text)
        # prefer keyword (more specific) then group
        paths = kw or grp["paths"]
        dtc_map.append({
            "dtc": code,
            "group": grp["group"],
            "keyword_paths": [path_str(x) for x in kw],
            "group_paths": [path_str(x) for x in grp["paths"]],
            "mapped_paths": [path_str(x) for x in paths],
        })

    qa_map = []
    for q in qa:
        texts = " ".join(q.get("comp_heads") or []) + " " + (q.get("report_short") or "")
        # report_short is a conclusion already stored in the public slice; used only for keyword mapping, not emitted
        kw = keyword_paths(texts)
        heads = [path_str(parse_path(h)) for h in (q.get("comp_heads") or [])]
        qa_map.append({
            "qid": q.get("qid"),
            "make_mapped": q.get("make_mapped"),
            "model_mapped": q.get("model_mapped"),
            "old_heads": heads,
            "fine_paths": [path_str(x) for x in kw],
            "dtcs": q.get("dtcs") or [],
        })

    mech_mapped_n = sum(1 for x in mech_map if x["mapped"])
    qa_fine_n = sum(1 for x in qa_map if x["fine_paths"])

    # QA ↔ NHTSA component (fine): qa fine path prefix-match a complaint/recall path in same model
    qa_to_comp_fine = 0
    official_paths_by_model = defaultdict(list)
    for r in complaints + recalls:
        official_paths_by_model[r["model"]].append((norm_space(r.get("comp_desc") or ""), parse_path(r.get("comp_desc") or "")))
    for q in qa_map:
        model = q["model_mapped"]
        for fp in q["fine_paths"]:
            fp_parts = parse_path(fp)
            if any(fine_match(fp_parts, op, fp, raw) for raw, op in official_paths_by_model.get(model, []) if op or raw):
                qa_to_comp_fine += 1
                break

    comparison = {
        "old": {
            "complaint_to_recall": old_rcl,
            "complaint_to_investigation": old_inv,
            "qa_to_component": old_qa,
            "complaint_to_dtc": old_dtc,
            "candidate_total": old_cand,
            "hard_total": old_hard,
            "hard_over_candidate": ratio_old,
            "review_10": old_review["counts"],
            "review_decisive_accepted_over_decisive": "2/4",
        },
        "new": {
            "complaint_to_recall_fine": len(fine_rcl),
            "complaint_to_recall_l1_only_excluded": len(coarse_rcl),
            "complaint_to_investigation_fine": len(fine_inv),
            "complaint_to_investigation_l1_only_excluded": len(coarse_inv),
            "qa_to_component_fine_lexicon": qa_to_comp_fine,
            "qa_to_component_old": old_qa,
            "complaint_to_dtc_unchanged": old_dtc,
            "candidate_total_if_replace_mmy_comp": new_cand_total_replace,
            "hard_total_previous_plus_tsb": new_hard_total,
            "new_hard_edges_tsb_recall": new_hard_tsb,
            "hard_over_candidate": round(ratio_new, 4) if ratio_new is not None else None,
            "fine_kinds_recall": dict(Counter(x["kind"] for x in fine_rcl)),
            "fine_kinds_inv": dict(Counter(x["kind"] for x in fine_inv)),
        },
        "deltas": {
            "recall_candidates": len(fine_rcl) - old_rcl,
            "inv_candidates": len(fine_inv) - old_inv,
            "core_mmy_comp": new_cand_core - old_core,
            "recall_reduction_rate": round(1 - len(fine_rcl) / old_rcl, 4) if old_rcl else None,
            "inv_reduction_rate": round(1 - len(fine_inv) / old_inv, 4) if old_inv else None,
        },
        "previous_review_survival": {
            "n": len(survival),
            "survives_fine": sum(1 for x in survival if x["survives_fine"]),
            "falls_to_l1_only": sum(1 for x in survival if x["falls_to_l1_only"]),
            "dropped_entirely": sum(1 for x in survival if not x["survives_fine"] and not x["falls_to_l1_only"]),
            "accepted_that_survive": [
                x for x in survival if x["old_judgment"] == "accepted" and x["survives_fine"]
            ],
            "accepted_that_drop_to_l1": [
                x for x in survival if x["old_judgment"] == "accepted" and x["falls_to_l1_only"]
            ],
            "rejected_that_survive": [
                x for x in survival if x["old_judgment"] == "rejected" and x["survives_fine"]
            ],
            "items": survival,
        },
        "mechanicdb": {
            "parts_n": len(mech_map),
            "parts_mapped_by_keyword": mech_mapped_n,
            "parts_mapped_rate": round(mech_mapped_n / max(len(mech_map), 1), 4),
            "dtc_n": len(dtc_map),
        },
        "qa": {
            "threads": len(qa_map),
            "with_fine_keyword_path": qa_fine_n,
            "fine_to_official_component": qa_to_comp_fine,
        },
        "rule": {
            "canonical_l1_aliases": L1_ALIAS,
            "fine_match": "exact path, or parent/child or common prefix with shared depth >= 2, after L1 aliasing",
            "l1_only_excluded_from_new_candidates": True,
        },
    }

    taxonomy = {
        "n_raw_path_rows": len(raw_paths),
        "n_distinct_canonical_paths": len({x["canonical"] for x in raw_paths}),
        "depth_histogram": {str(k): v for k, v in sorted(depth_hist.items())},
        "l1_histogram": dict(l1_hist.most_common()),
        "paths": [
            {"canonical": k[0], "depth": k[1], "l1": k[2], "rows": v}
            for k, v in tax_counter.most_common()
        ],
        "dtc_group_table": {k: {"name": v[0], "paths": v[1]} for k, v in DTC_GROUP.items()},
        "dtc_letter": DTC_LETTER,
    }

    # Deterministic sample of 10 fine recall candidates for review.
    # Stratify by campaign and kind, then hash-stable pick.
    by_camp = defaultdict(list)
    for x in fine_rcl:
        by_camp[x["target_id"]].append(x)
    sample = []
    camps = sorted(by_camp)
    # round-robin across campaigns, preferring diversity of kinds
    pointers = {c: 0 for c in camps}
    for c in camps:
        by_camp[c].sort(key=lambda x: (x["kind"], x["odino"]))
    while len(sample) < 10 and any(pointers[c] < len(by_camp[c]) for c in camps):
        for c in camps:
            if pointers[c] < len(by_camp[c]) and len(sample) < 10:
                sample.append(by_camp[c][pointers[c]])
                pointers[c] += 1
    # attach official recall excerpt (already public in slice) and raw component labels
    review_items = []
    for x in sample:
        rec = rcl_idx[x["target_id"]]
        excerpt = (rec.get("defect_summary") or "")[:280]
        review_items.append({
            "odino": x["odino"],
            "campno": x["target_id"],
            "model": x["model"],
            "kind": x["kind"],
            "score": x["score"],
            "shared": x["shared"],
            "shared_depth": x["shared_depth"],
            "complaint_paths": x["complaint_paths"],
            "recall_paths": x["target_paths"],
            "recall_defect_excerpt": excerpt,
            "judgment": "",  # filled in review_step2.py / this file after
            "reason": "",
            "basis": "Only complaint component labels and official recall defect text; complaint narratives were not used.",
        })

    (OUT / "component_taxonomy.json").write_text(json.dumps(taxonomy, ensure_ascii=False, indent=2))
    (OUT / "scheme2_comparison.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2))
    (OUT / "candidates_v2_fine_recall.json").write_text(
        json.dumps({"n": len(fine_rcl), "items": fine_rcl}, ensure_ascii=False, indent=2)
    )
    (OUT / "candidates_v2_fine_inv.json").write_text(
        json.dumps({"n": len(fine_inv), "items": fine_inv}, ensure_ascii=False, indent=2)
    )
    (OUT / "candidates_v2_coarse_only.json").write_text(
        json.dumps({"recall_l1_only": len(coarse_rcl), "inv_l1_only": len(coarse_inv)}, ensure_ascii=False, indent=2)
    )
    (REVIEW_OUT / "review_10_v2_unjudged.json").write_text(
        json.dumps({"n": len(review_items), "items": review_items}, ensure_ascii=False, indent=2)
    )
    (OUT / "mechanic_qa_path_map_counts.json").write_text(json.dumps({
        "mechanic_parts_mapped_rate": comparison["mechanicdb"]["parts_mapped_rate"],
        "mechanic_parts_mapped": mech_mapped_n,
        "mechanic_parts_n": len(mech_map),
        "sample_mapped_part_names": [x["name"] for x in mech_map if x["mapped"]][:20],
        "sample_unmapped_part_names": [x["name"] for x in mech_map if not x["mapped"]][:20],
        "qa_fine": qa_fine_n,
        "qa_threads": len(qa_map),
        "dtc_sample": dtc_map[:15],
    }, ensure_ascii=False, indent=2))

    print("TAXONOMY distinct paths", taxonomy["n_distinct_canonical_paths"], "depth", taxonomy["depth_histogram"])
    print("FINE recall", len(fine_rcl), "coarse_only", len(coarse_rcl), "old", old_rcl)
    print("FINE inv", len(fine_inv), "coarse_only", len(coarse_inv), "old", old_inv)
    print("kinds", comparison["new"]["fine_kinds_recall"], comparison["new"]["fine_kinds_inv"])
    print("hard+tsb", new_hard_total, "ratio", comparison["new"]["hard_over_candidate"])
    print("survival", json.dumps(comparison["previous_review_survival"], ensure_ascii=False)[:2000])
    print("review sample odinos", [(x["odino"], x["campno"], x["kind"], x["shared"]) for x in review_items])
    print("mech mapped", mech_mapped_n, "/", len(mech_map), "qa fine", qa_fine_n)
    print("DONE")


if __name__ == "__main__":
    main()
