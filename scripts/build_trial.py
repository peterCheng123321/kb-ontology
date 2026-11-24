#!/usr/bin/env python3
"""用公开数据构建本田 2018 试验图（内存与磁盘）。不写入车辆识别号，不写入投诉叙述原文。"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD

# 路径相对于仓库根目录。公开切片放在 data/honda-2018/（不进 git）。
REPO_ROOT = Path(__file__).resolve().parents[1]
DATA = REPO_ROOT / "data" / "honda-2018"
RDFDIR = REPO_ROOT / "rdf"
QDIR = REPO_ROOT / "queries"
REV = REPO_ROOT / "review"
for p in (RDFDIR, QDIR, REV):
    p.mkdir(parents=True, exist_ok=True)

DEMO = Namespace("https://w3id.org/poc-kb/demo/")
NS = "https://w3id.org/poc-kb/demo/"

ZH_LABEL = {
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
    "BACK OVER PREVENTION": "倒车防撞/后视",
    "EXTERIOR LIGHTING": "外部灯光",
    "SUSPENSION": "悬挂",
    "WHEELS": "轮毂",
    "TIRES": "轮胎",
}

HEAD_ALIASES = {
    "FUEL": "FUEL SYSTEM",
    "FUEL/PROPULSION SYSTEM": "FUEL SYSTEM",
    "ENGINE AND ENGINE COOLING": "ENGINE",
}


def canon_head(h: str) -> str:
    h = (h or "").upper().strip()
    if not h:
        return ""
    if "," in h:
        h = h.split(",")[0].strip()
    return HEAD_ALIASES.get(h, h)


def slug(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", (s or "").strip())
    return s.strip("_") or "na"


def iri(*parts: str) -> URIRef:
    return URIRef(NS + "/".join(parts))


slice_ = json.loads((DATA / "slice_nhtsa_qa.json").read_text())
mech = json.loads((DATA / "mechanicdb.json").read_text())
codes_rows = json.loads((DATA / "dtc_codeslist.json").read_text())

codes_by = {}
for r in codes_rows:
    c = str(r.get("code") or "").strip().upper()
    if c:
        codes_by[c] = r

mech_codes = {}
for r in mech["dtc_codes"]:
    c = str(r.get("dtc_code") or r.get("code") or "").strip().upper()
    if c:
        mech_codes[c] = r

# join fixes to codes and parts
# inspect keys once
fix_by_id = {}
for r in mech["fixes"]:
    fid = str(r.get("fix_id") or "").strip()
    if fid:
        fix_by_id[fid] = r

code_to_fix_ids = defaultdict(list)
part_rows = {}
fix_to_parts = defaultdict(list)
# joined table may have dtc_code, fix_id, part fields
for r in mech["joined"]:
    code = str(r.get("dtc_code") or r.get("code") or "").strip().upper()
    fid = str(r.get("fix_id") or "").strip()
    if code and fid and fid not in code_to_fix_ids[code]:
        code_to_fix_ids[code].append(fid)

# parts
for r in mech["parts"]:
    pid = str(r.get("part_id") or "").strip()
    if pid:
        part_rows[pid] = r

# Parts table is keyed by fix_id (joined table has no part_id).
for r in mech["parts"]:
    fid = str(r.get("fix_id") or "").strip()
    pid = str(r.get("part_id") or "").strip()
    if fid and pid and pid not in fix_to_parts[fid]:
        fix_to_parts[fid].append(pid)

# If still empty, attach all parts listed on joined rows by name later
# Also check fixes for part ids? skip

complaints = slice_["complaints"]
recalls = slice_["recalls"]
invs = slice_["investigations"]
qa = slice_["qa"]

# fold complaints by odino
by_odino = defaultdict(list)
for r in complaints:
    by_odino[r["odino"]].append(r)

# fold recalls by campno
by_camp = defaultdict(list)
for r in recalls:
    by_camp[r["campno"]].append(r)

# fold inv by action
by_act = defaultdict(list)
for r in invs:
    by_act[r["action_number"]].append(r)

# DTC set used in slice
used_dtcs = set()
for r in complaints:
    used_dtcs.update(r["dtcs"])
for r in qa:
    used_dtcs.update(r["dtcs"])

# ---------- graph ----------
g = Graph()
g.bind("demo", DEMO)
g.bind("rdf", RDF)
g.bind("rdfs", RDFS)
g.bind("xsd", XSD)

def add_literal(s, p, val, typ=XSD.string):
    if val is None or val == "":
        return
    if typ in (XSD.integer,):
        g.add((s, p, Literal(int(val), datatype=typ)))
    elif typ in (XSD.decimal,):
        g.add((s, p, Literal(Decimal(str(val)), datatype=typ)))
    elif typ is XSD.boolean:
        g.add((s, p, Literal(bool(val), datatype=typ)))
    elif typ is XSD.float:
        g.add((s, p, Literal(float(val), datatype=typ)))
    else:
        g.add((s, p, Literal(str(val), datatype=typ)))


# Vehicles
vehicles = {}
for make, model, year in {("HONDA", "CR-V", "2018"), ("HONDA", "ACCORD", "2018")}:
    u = iri("vehicle", f"{make}_{slug(model)}_{year}")
    vehicles[(make, model, year)] = u
    g.add((u, RDF.type, DEMO.VehicleModelYear))
    add_literal(u, DEMO.make, make)
    add_literal(u, DEMO.model, model)
    add_literal(u, DEMO.modelYear, year)
    g.add((u, RDFS.label, Literal(f"{make} {model} {year}")))

# Components (canonical heads that appear)
comp_iris = {}
all_heads = set()
for r in complaints + recalls + invs:
    all_heads.add(canon_head(r["comp_head"]))
for r in qa:
    all_heads.update(r["comp_heads"])
all_heads.discard("")

for h in sorted(all_heads):
    u = iri("component", slug(h))
    comp_iris[h] = u
    g.add((u, RDF.type, DEMO.Component))
    add_literal(u, DEMO.head, h)
    add_literal(u, DEMO.labelEn, h)
    if h in ZH_LABEL:
        add_literal(u, DEMO.labelZh, ZH_LABEL[h])
    g.add((u, RDFS.label, Literal(h)))

# Recalls
recall_iris = {}
recall_meta = {}
for campno, rows in by_camp.items():
    u = iri("recall", campno)
    recall_iris[campno] = u
    g.add((u, RDF.type, DEMO.Recall))
    add_literal(u, DEMO.campno, campno)
    r0 = rows[0]
    # official texts, not consumer narratives
    defect = (r0.get("defect_summary") or "").strip()
    remedy = (r0.get("corrective_action") or "").strip()
    add_literal(u, DEMO.defectSummary, defect)
    add_literal(u, DEMO.correctiveAction, remedy)
    pot = r0.get("potaff") or ""
    if pot.isdigit():
        add_literal(u, DEMO.potentiallyAffected, pot, XSD.integer)
    models = sorted({(r["make"], r["model"], r["year"]) for r in rows})
    heads = sorted({canon_head(r["comp_head"]) for r in rows if canon_head(r["comp_head"])})
    exacts = {(r["make"], r["model"], r["year"], r["comp_desc"]) for r in rows}
    for mk, md, yr in models:
        g.add((u, DEMO.coversVehicle, vehicles[(mk, md, yr)]))
    for h in heads:
        g.add((u, DEMO.hasComponent, comp_iris[h]))
    g.add((u, RDFS.label, Literal(f"Recall {campno}")))
    recall_meta[campno] = {
        "models": models,
        "heads": set(heads),
        "exacts": exacts,
        "defect": defect,
        "remedy": remedy,
        "raw_heads": sorted({r["comp_head"] for r in rows}),
        "comp_descs": sorted({r["comp_desc"] for r in rows}),
    }

# Investigations
inv_iris = {}
inv_meta = {}
hard_inv_recall = 0
for action, rows in by_act.items():
    u = iri("investigation", action)
    inv_iris[action] = u
    g.add((u, RDF.type, DEMO.Investigation))
    add_literal(u, DEMO.actionNumber, action)
    prefix = re.match(r"[A-Z]+", action)
    add_literal(u, DEMO.actionType, prefix.group(0) if prefix else "")
    add_literal(u, DEMO.subject, rows[0].get("subject") or "")
    add_literal(u, DEMO.summary, rows[0].get("summary") or "")
    campnos = {r["campno"] for r in rows if r.get("campno")}
    for c in campnos:
        if c in recall_iris:
            g.add((u, DEMO.campaign, recall_iris[c]))
            hard_inv_recall += 1
    for mk, md, yr in {(r["make"], r["model"], r["year"]) for r in rows}:
        g.add((u, DEMO.coversVehicle, vehicles[(mk, md, yr)]))
    heads = sorted({canon_head(r["comp_head"]) for r in rows if canon_head(r["comp_head"])})
    for h in heads:
        g.add((u, DEMO.hasComponent, comp_iris[h]))
    g.add((u, RDFS.label, Literal(f"Investigation {action}")))
    inv_meta[action] = {
        "campnos": campnos,
        "models": {(r["make"], r["model"], r["year"]) for r in rows},
        "heads": set(heads),
        "subject": rows[0].get("subject") or "",
    }

# DTCs + repair steps + parts (only codes used in slice, plus any mechanic-linked)
hard_dtc_step = 0
hard_step_part = 0
dtc_iris = {}
step_iris = {}
part_iris = {}

# include mechanic codes that appear in slice
for code in sorted(used_dtcs):
    u = iri("dtc", code)
    dtc_iris[code] = u
    g.add((u, RDF.type, DEMO.DTC))
    add_literal(u, DEMO.code, code)
    info = codes_by.get(code) or {}
    add_literal(u, DEMO.description, info.get("description") or "")
    add_literal(u, DEMO.category, info.get("category") or "")
    add_literal(u, DEMO.inCodesList, code in codes_by, XSD.boolean)
    add_literal(u, DEMO.inMechanicSample, code in mech_codes, XSD.boolean)
    g.add((u, RDFS.label, Literal(code)))

    if code in code_to_fix_ids:
        for fid in code_to_fix_ids[code]:
            fx = fix_by_id.get(fid) or {}
            su = iri("repair-step", slug(fid))
            step_iris[fid] = su
            g.add((su, RDF.type, DEMO.RepairStep))
            add_literal(su, DEMO.fixId, fid)
            title = fx.get("fix_title") or fx.get("title") or fid
            add_literal(su, DEMO.title, title)
            add_literal(su, DEMO.difficulty, fx.get("difficulty_level") or fx.get("difficulty") or "")
            labor = fx.get("est_labor_hours") or fx.get("labor_hours")
            if labor not in (None, ""):
                try:
                    add_literal(su, DEMO.laborHours, float(labor), XSD.float)
                except Exception:
                    pass
            g.add((su, DEMO.forDtc, u))
            hard_dtc_step += 1
            g.add((su, RDFS.label, Literal(str(title)[:80])))
            for pid in fix_to_parts.get(fid, []):
                pr = part_rows.get(pid) or {}
                pu = iri("part", slug(pid))
                if pid not in part_iris:
                    part_iris[pid] = pu
                    g.add((pu, RDF.type, DEMO.Part))
                    pname = pr.get("part_name") or pid
                    add_literal(pu, DEMO.partName, pname)
                    g.add((pu, RDFS.label, Literal(str(pname)[:80])))
                g.add((su, DEMO.usesPart, part_iris[pid]))
                hard_step_part += 1

# Complaints
complaint_iris = {}
for odino, rows in by_odino.items():
    u = iri("complaint", odino)
    complaint_iris[odino] = u
    g.add((u, RDF.type, DEMO.Complaint))
    add_literal(u, DEMO.odino, odino)
    r0 = rows[0]
    g.add((u, DEMO.vehicle, vehicles[(r0["make"], r0["model"], r0["year"])]))
    heads = {canon_head(r["comp_head"]) for r in rows if canon_head(r["comp_head"])}
    for h in heads:
        g.add((u, DEMO.hasComponent, comp_iris[h]))
    dtcs = set()
    for r in rows:
        dtcs.update(r["dtcs"])
    for c in dtcs:
        if c in dtc_iris:
            g.add((u, DEMO.mentionsDtc, dtc_iris[c]))
    add_literal(u, DEMO.receivedDate, r0.get("received_date") or "")
    add_literal(u, DEMO.crashFlag, r0.get("crash") or "")
    add_literal(u, DEMO.fireFlag, r0.get("fire") or "")
    g.add((u, RDFS.label, Literal(f"Complaint {odino} {r0['make']} {r0['model']} {r0['year']}")))

# QA
qa_iris = {}
for r in qa:
    qid = r["qid"] or slug(r["brand_raw"] + r["model_raw"])
    u = iri("qa", slug(qid))
    qa_iris[r["qid"]] = u
    g.add((u, RDF.type, DEMO.NamedThing))  # no dedicated class required in queries; add type comment
    # use a subclass-like type via extra class? Schema has no QA class. Keep as NamedThing + label.
    g.add((u, RDF.type, URIRef(NS + "QaThread")))
    g.add((u, RDFS.label, Literal(f"QA {qid} {r['brand_raw']} {r['model_raw']}")))
    add_literal(u, DEMO.brandRaw, r["brand_raw"])
    add_literal(u, DEMO.modelRaw, r["model_raw"])
    add_literal(u, DEMO.makeMapped, r["make_mapped"])
    add_literal(u, DEMO.modelMapped, r["model_mapped"])
    add_literal(u, DEMO.reportShort, r.get("report_short") or "")
    for h in r["comp_heads"]:
        ch = canon_head(h) or h
        if ch in comp_iris:
            g.add((u, DEMO.hasComponent, comp_iris[ch]))

# ---------- Candidate links ----------
def add_link(lid, frm, to, method, score, status="unreviewed", head="", note=""):
    u = iri("link", slug(lid))
    g.add((u, RDF.type, DEMO.CandidateLink))
    g.add((u, DEMO.fromEntity, frm))
    g.add((u, DEMO.toEntity, to))
    add_literal(u, DEMO.method, method)
    add_literal(u, DEMO.score, f"{score:.2f}", XSD.decimal)
    add_literal(u, DEMO.reviewStatus, status)
    if head:
        add_literal(u, DEMO.matchedHead, head)
    if note:
        add_literal(u, DEMO.note, note)
    g.add((u, RDFS.label, Literal(f"{method} {score:.2f} {status}")))
    return u


# Pre-choose 10 review keys (odino, campno) after we know they exist.
# We'll assign status in a dict once we build the pool.

cand_recall = []  # dicts
# For each odino, each campaign covering same MMY
for odino, rows in by_odino.items():
    make, model, year = rows[0]["make"], rows[0]["model"], rows[0]["year"]
    exacts = {r["comp_desc"] for r in rows}
    heads = {canon_head(r["comp_head"]) for r in rows}
    head_raw = defaultdict(set)
    for r in rows:
        head_raw[canon_head(r["comp_head"])].add(r["comp_desc"])
    for campno, meta in recall_meta.items():
        if (make, model, year) not in meta["models"]:
            continue
        shared_heads = heads & meta["heads"]
        if not shared_heads:
            continue
        exact_hit = any((make, model, year, desc) in meta["exacts"] for desc in exacts)
        method = "mmy_comp_exact" if exact_hit else "mmy_comp_head"
        score = 0.90 if exact_hit else 0.60
        matched = sorted(shared_heads)
        cand_recall.append({
            "odino": odino, "campno": campno, "make": make, "model": model,
            "method": method, "score": score, "heads": matched,
            "complaint_descs": sorted(exacts),
            "recall_descs": meta["comp_descs"],
            "defect": meta["defect"][:280],
            "remedy": meta["remedy"][:180],
        })

cand_inv = []
for odino, rows in by_odino.items():
    make, model, year = rows[0]["make"], rows[0]["model"], rows[0]["year"]
    heads = {canon_head(r["comp_head"]) for r in rows}
    for action, meta in inv_meta.items():
        if (make, model, year) not in meta["models"]:
            continue
        shared = heads & meta["heads"]
        if not shared:
            continue
        cand_inv.append({
            "odino": odino, "action": action, "make": make, "model": model,
            "method": "mmy_comp_head", "score": 0.60, "heads": sorted(shared),
            "subject": meta["subject"],
        })

cand_qa = []
for r in qa:
    for h in r["comp_heads"]:
        ch = canon_head(h) or h
        if ch in comp_iris:
            cand_qa.append({
                "qid": r["qid"], "head": ch, "model": r["model_mapped"],
                "brand_raw": r["brand_raw"], "model_raw": r["model_raw"],
                "method": "qa_zh_lexicon", "score": 0.50,
            })

# DTC co-occur links (complaint -> dtc already as mentionsDtc; also CandidateLink for transparency)
cand_dtc = []
for odino, rows in by_odino.items():
    for r in rows:
        ch = canon_head(r["comp_head"])
        for code in r["dtcs"]:
            if code in dtc_iris and ch in comp_iris:
                cand_dtc.append({
                    "odino": odino, "code": code, "head": ch, "model": r["model"],
                    "method": "dtc_regex_cooccur", "score": 0.70,
                })

# ---- pick 10 recall candidates for human review (diverse, real edges) ----
# Prefer one of each interesting head, mix exact/head, both models.
def pick_review(cands, n=10):
    picked = []
    used_odino = set()
    wanted = [
        ("STEERING", "CR-V", "18V663000"),
        ("BACK OVER PREVENTION", "ACCORD", "18V629000"),
        ("VISIBILITY", "ACCORD", "18V629000"),
        ("FUEL SYSTEM", "ACCORD", "20V314000"),
        ("FUEL SYSTEM", "CR-V", "23V858000"),
        ("SEAT BELTS", "CR-V", "23V158000"),
        ("AIR BAGS", "ACCORD", "26V332000"),
        ("ELECTRICAL SYSTEM", "ACCORD", "20V771000"),
        ("EXTERIOR LIGHTING", "ACCORD", "20V771000"),
        ("VISIBILITY", "ACCORD", "20V771000"),
    ]
    index = {(c["odino"], c["campno"], h): c for c in cands for h in c["heads"]}
    # fallback lists by (head, model, campno)
    by_key = defaultdict(list)
    for c in cands:
        for h in c["heads"]:
            by_key[(h, c["model"], c["campno"])].append(c)
    for h, model, camp in wanted:
        opts = [c for c in by_key.get((h, model, camp), []) if c["odino"] not in used_odino]
        # prefer exact method
        opts.sort(key=lambda c: (0 if c["method"] == "mmy_comp_exact" else 1, c["odino"]))
        if opts:
            c = opts[0]
            picked.append(c)
            used_odino.add(c["odino"])
    return picked[:n]


review_targets = pick_review(cand_recall, 10)

# Human judgments (component label + official recall text only; narratives were not read).
# Keyed by (head preference, campno, model) then applied to picked odino.
JUDGE = {
    # tiny-population EPS gearbox magnet recall vs any steering complaint
    ("STEERING", "18V663000"): (
        "rejected",
        "召回是极小范围（电子助力转向扭矩传感器磁铁/转向齿轮箱，潜在影响约 54 辆）。仅凭转向主类，无法把该年款大量转向投诉接到这次召回。过宽。",
    ),
    ("BACK OVER PREVENTION", "18V629000"): (
        "accepted",
        "投诉部件主类是倒车防撞/后视，召回是备份摄像头中控显示故障，功能同一类，候选成立（仍非官方已确认同一缺陷）。",
    ),
    ("VISIBILITY", "18V629000"): (
        "uncertain",
        "召回是备份摄像头显示；VISIBILITY 还包含玻璃、雨刷等。主类过宽，无法确认。",
    ),
    ("FUEL SYSTEM", "20V314000"): (
        "uncertain",
        "召回是燃油泵总成。燃油系统主类方向对，但本切片大量燃油/失火类投诉不一定是油泵缺陷。字段级只能算弱相关。",
    ),
    ("FUEL SYSTEM", "23V858000"): (
        "uncertain",
        "同样是燃油泵模块召回。主类对齐，但不能根据主类断定该投诉就是油泵问题。",
    ),
    ("SEAT BELTS", "23V158000"): (
        "accepted",
        "投诉部件主类为安全带，召回是前排安全带锁扣按钮/锁扣总成，部件同类，候选看起来合理。",
    ),
    ("AIR BAGS", "26V332000"): (
        "uncertain",
        "召回是座椅重量传感器（影响气囊乘员分类），投诉主类是气囊。有关联但不等于同一零件，字段不足以确认。",
    ),
    ("ELECTRICAL SYSTEM", "20V771000"): (
        "rejected",
        "召回是 BCM 软件通信中断（可影响显示/灯光等）。电气系统主类覆盖过宽（本切片该主类投诉号四百以上），不能据此连接。",
    ),
    ("EXTERIOR LIGHTING", "20V771000"): (
        "uncertain",
        "召回文本涉及车身控制模块通信，覆盖行含外部灯光。可能相关，但仅凭主类不能确认是同一问题。",
    ),
    ("VISIBILITY", "20V771000"): (
        "uncertain",
        "召回是 BCM 软件通信中断，覆盖行含视野/显示相关部件。可能波及中控/影像显示，但 VISIBILITY 主类仍过宽，不能确认。",
    ),
}

# apply
review_records = []
review_map = {}  # (odino, campno) -> status
for c in review_targets:
    # choose the wanted head if several
    status, reason = "unreviewed", "未覆盖的抽样规则"
    chosen_head = c["heads"][0]
    for h in c["heads"]:
        if (h, c["campno"]) in JUDGE:
            status, reason = JUDGE[(h, c["campno"])]
            chosen_head = h
            break
    review_map[(c["odino"], c["campno"])] = status
    review_records.append({
        "odino": c["odino"],
        "campno": c["campno"],
        "model": c["model"],
        "method": c["method"],
        "score": c["score"],
        "matched_heads": c["heads"],
        "judge_head": chosen_head,
        "complaint_component_values": c["complaint_descs"],
        "recall_component_values": c["recall_descs"],
        "recall_defect_excerpt": c["defect"],
        "judgment": status,
        "reason": reason,
        "basis": "Only complaint component labels and official recall defect text; complaint narratives were not used.",
    })

# add all links to graph
n_cand_recall = n_cand_inv = n_cand_qa = n_cand_dtc = 0
for c in cand_recall:
    st = review_map.get((c["odino"], c["campno"]), "unreviewed")
    add_link(
        f"cr-{c['odino']}-{c['campno']}",
        complaint_iris[c["odino"]],
        recall_iris[c["campno"]],
        c["method"], c["score"], st,
        head=", ".join(c["heads"]),
    )
    n_cand_recall += 1

for c in cand_inv:
    add_link(
        f"ci-{c['odino']}-{c['action']}",
        complaint_iris[c["odino"]],
        inv_iris[c["action"]],
        c["method"], c["score"], "unreviewed",
        head=", ".join(c["heads"]),
    )
    n_cand_inv += 1

for c in cand_qa:
    add_link(
        f"qc-{c['qid']}-{slug(c['head'])}",
        qa_iris[c["qid"]],
        comp_iris[c["head"]],
        c["method"], c["score"], "unreviewed",
        head=c["head"],
    )
    n_cand_qa += 1

# de-dup dtc links per odino-code-head
seen_dtc = set()
for c in cand_dtc:
    key = (c["odino"], c["code"], c["head"])
    if key in seen_dtc:
        continue
    seen_dtc.add(key)
    add_link(
        f"cd-{c['odino']}-{c['code']}-{slug(c['head'])}",
        complaint_iris[c["odino"]],
        dtc_iris[c["code"]],
        c["method"], c["score"], "unreviewed",
        head=c["head"],
    )
    n_cand_dtc += 1

# counts
def count_type(cls):
    return len(list(g.subjects(RDF.type, cls)))

stats = {
    "slice": "HONDA CR-V + ACCORD 2018",
    "measured_at": "2026-11-24 Asia/Shanghai",
    "nodes": {
        "VehicleModelYear": count_type(DEMO.VehicleModelYear),
        "Complaint": count_type(DEMO.Complaint),
        "Recall": count_type(DEMO.Recall),
        "Investigation": count_type(DEMO.Investigation),
        "Component": count_type(DEMO.Component),
        "DTC": count_type(DEMO.DTC),
        "RepairStep": count_type(DEMO.RepairStep),
        "Part": count_type(DEMO.Part),
        "CandidateLink": count_type(DEMO.CandidateLink),
        "QaThread": count_type(URIRef(NS + "QaThread")),
    },
    "hard_edges": {
        "investigation_to_recall_via_CAMPNO": hard_inv_recall,
        "dtc_to_repair_step": hard_dtc_step,
        "repair_step_to_part": hard_step_part,
        "hard_total": hard_inv_recall + hard_dtc_step + hard_step_part,
    },
    "candidate_edges": {
        "complaint_to_recall_mmy_component": n_cand_recall,
        "complaint_to_investigation_mmy_component": n_cand_inv,
        "qa_to_component_lexicon": n_cand_qa,
        "complaint_to_dtc_regex_cooccur": n_cand_dtc,
        "candidate_total": n_cand_recall + n_cand_inv + n_cand_qa + n_cand_dtc,
    },
    "ratios": {},
    "notes": {
        "inv_actions": list(inv_meta),
        "inv_all_campno_empty": all(not m["campnos"] for m in inv_meta.values()),
        "recall_campaigns": list(recall_iris),
        "complaints_with_dtc": sum(1 for rows in by_odino.values() if any(r["dtcs"] for r in rows)),
        "dtcs_in_slice": sorted(used_dtcs),
        "dtcs_in_mechanic_and_slice": sorted(used_dtcs & set(mech_codes)),
        "canonical_head_rule": "strip after comma; map FUEL and FUEL/PROPULSION SYSTEM to FUEL SYSTEM; ENGINE AND ENGINE COOLING to ENGINE",
    },
}
ht = stats["hard_edges"]["hard_total"]
ct = stats["candidate_edges"]["candidate_total"]
stats["ratios"] = {
    "hard_over_candidate": None if ct == 0 else round(ht / ct, 4),
    "hard_share_of_all_edges": None if (ht + ct) == 0 else round(ht / (ht + ct), 4),
    "candidate_share_of_all_edges": None if (ht + ct) == 0 else round(ct / (ht + ct), 4),
    "hard_total": ht,
    "candidate_total": ct,
    "all_scored_or_hard_edges": ht + ct,
}

# serialize TTL (abox only; tbox is separate)
abox_path = RDFDIR / "honda_2018_abox.ttl"
g.serialize(abox_path, format="turtle")
(DATA / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
(REV / "review_10.json").write_text(json.dumps({
    "protocol": "Judged from complaint component labels and official NHTSA recall defect text only. Complaint narratives were not stored or read. accepted means the candidate looks plausible at field level, not that NHTSA confirmed causation.",
    "n": len(review_records),
    "counts": dict(Counter(r["judgment"] for r in review_records)),
    "items": review_records,
}, ensure_ascii=False, indent=2), encoding="utf-8")

# also keep a compact link dump for queries without re-parsing huge ttl comments
(DATA / "link_summaries.json").write_text(json.dumps({
    "showcase_odino": "11407338",
    "recall_candidates_n": n_cand_recall,
    "inv_candidates_n": n_cand_inv,
}, ensure_ascii=False), encoding="utf-8")

print("nodes", stats["nodes"])
print("hard", stats["hard_edges"])
print("cand", stats["candidate_edges"])
print("ratios", stats["ratios"])
print("review", Counter(r["judgment"] for r in review_records), "n", len(review_records))
print("abox triples", len(g), "bytes", abox_path.stat().st_size)
print("review odinos", [(r["odino"], r["model"], r["campno"], r["judge_head"], r["judgment"]) for r in review_records])

# ----- SPARQL on the in-memory graph (avoid re-parsing the 4MB TTL) -----
import pickle
pickle_path = RDFDIR / "honda_2018_abox.pkl"
with pickle_path.open("wb") as fh:
    pickle.dump(g, fh, protocol=4)

queries = {
"Q1_complaint_component_recall": '''
PREFIX demo: <https://w3id.org/poc-kb/demo/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?odino ?modelYearLabel ?head ?campno ?score ?method ?review ?remedy
WHERE {
  VALUES ?odino { "11324947" "11499094" }
  ?c a demo:Complaint ; demo:odino ?odino ; demo:vehicle ?v ; demo:hasComponent ?comp .
  ?v rdfs:label ?modelYearLabel .
  ?comp demo:head ?head .
  ?link a demo:CandidateLink ;
        demo:fromEntity ?c ; demo:toEntity ?r ;
        demo:method ?method ; demo:score ?score ;
        demo:reviewStatus ?review ; demo:matchedHead ?mh .
  ?r a demo:Recall ; demo:campno ?campno ; demo:correctiveAction ?remedy ; demo:hasComponent ?comp .
  FILTER(CONTAINS(?mh, ?head))
}
ORDER BY ?odino ?campno ?head
''',
"Q2_investigation_to_recall_hard": '''
PREFIX demo: <https://w3id.org/poc-kb/demo/>
SELECT ?action ?subject ?campno
WHERE {
  ?i a demo:Investigation ; demo:actionNumber ?action ; demo:subject ?subject .
  OPTIONAL { ?i demo:campaign ?r . ?r demo:campno ?campno . }
}
ORDER BY ?action
''',
"Q3_component_dtc_repair_part": '''
PREFIX demo: <https://w3id.org/poc-kb/demo/>
SELECT ?head ?odino ?code ?inCodes ?inMech ?fixTitle ?partName
WHERE {
  VALUES ?odino { "11407338" }
  ?c a demo:Complaint ; demo:odino ?odino ; demo:hasComponent ?comp ; demo:mentionsDtc ?dtc .
  ?comp demo:head "FUEL SYSTEM" ; demo:head ?head .
  ?dtc demo:code ?code ; demo:inCodesList ?inCodes ; demo:inMechanicSample ?inMech .
  OPTIONAL {
    ?step demo:forDtc ?dtc ; demo:title ?fixTitle .
    OPTIONAL { ?step demo:usesPart ?part . ?part demo:partName ?partName . }
  }
}
ORDER BY ?code ?fixTitle ?partName
LIMIT 12
''',
"Q4_qa_component_complaint_count": '''
PREFIX demo: <https://w3id.org/poc-kb/demo/>
SELECT ?qid ?brand ?model ?head ?nComplaints
WHERE {
  VALUES ?qid { "Q70024" "Q70083" }
  ?q a demo:QaThread ;
     demo:brandRaw ?brand ; demo:modelRaw ?model ; demo:hasComponent ?comp .
  FILTER(STRAFTER(STR(?q), "/qa/") = ?qid)
  ?comp demo:head ?head .
  {
    SELECT ?comp (COUNT(DISTINCT ?c) AS ?nComplaints)
    WHERE { ?c a demo:Complaint ; demo:hasComponent ?comp . }
    GROUP BY ?comp
  }
}
ORDER BY ?qid ?head
''',
"Q5_complaint_to_investigation_no_recall": '''
PREFIX demo: <https://w3id.org/poc-kb/demo/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?odino ?vehicle ?head ?action ?subject ?hasCampaign
WHERE {
  VALUES ?odino { "11407338" }
  ?c a demo:Complaint ; demo:odino ?odino ; demo:vehicle ?v .
  ?v rdfs:label ?vehicle .
  ?link a demo:CandidateLink ; demo:fromEntity ?c ; demo:toEntity ?i ; demo:matchedHead ?head .
  ?i a demo:Investigation ; demo:actionNumber ?action ; demo:subject ?subject .
  BIND(EXISTS { ?i demo:campaign ?any } AS ?hasCampaign)
}
ORDER BY ?action
''',
}

for name, q in queries.items():
    (QDIR / f"{name}.rq").write_text(q.strip() + "\n", encoding="utf-8")

sparql_out = {"shacl_conforms": True, "shacl_file": "rdf/shacl_report.txt", "queries": {}}
for name, q in queries.items():
    recs = []
    for row in g.query(q):
        recs.append({str(v): ("" if row[v] is None else str(row[v])[:400]) for v in row.labels})
    sparql_out["queries"][name] = {"n": len(recs), "rows": recs}
    print(f"SPARQL {name} n={len(recs)}")

(QDIR / "sparql_results.json").write_text(json.dumps(sparql_out, ensure_ascii=False, indent=2), encoding="utf-8")

# ----- PNG: most complete chain around complaint 11407338 -----
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx

SHOW = "11407338"
# Collect neighbors of this complaint from in-memory structures
comp_nodes = []
if SHOW in by_odino:
    heads = sorted({canon_head(r["comp_head"]) for r in by_odino[SHOW] if canon_head(r["comp_head"])})
    dtcs = sorted({d for r in by_odino[SHOW] for d in r["dtcs"]})
    model = by_odino[SHOW][0]["model"]
else:
    heads, dtcs, model = [], [], "?"

G = nx.DiGraph()

def addn(nid, label, kind, **attrs):
    G.add_node(nid, label=label, kind=kind, **attrs)

addn("v", f"HONDA {model} 2018", "vehicle")
addn("c", f"Complaint\nODINO {SHOW}", "complaint")
G.add_edge("c", "v", label="vehicle", style="hard")

for h in heads:
    hid = f"comp:{h}"
    addn(hid, f"Component\n{h}", "component")
    G.add_edge("c", hid, label="hasComponent", style="hard")

# recall candidates
for cnd in cand_recall:
    if cnd["odino"] != SHOW:
        continue
    rid = f"rcl:{cnd['campno']}"
    addn(rid, f"Recall\n{cnd['campno']}", "recall")
    G.add_edge("c", rid, label=f"candidate {cnd['score']:.2f}\n{cnd['method']}", style="candidate")
    for h in cnd["heads"]:
        hid = f"comp:{h}"
        if hid in G:
            G.add_edge(rid, hid, label="covers", style="hard")

# investigations
for cnd in cand_inv:
    if cnd["odino"] != SHOW:
        continue
    iid = f"inv:{cnd['action']}"
    addn(iid, f"Investigation\n{cnd['action']}\n(no CAMPNO)", "investigation")
    G.add_edge("c", iid, label=f"candidate {cnd['score']:.2f}", style="candidate")
    # broken: no edge to recall
    addn("brk", "Recall via CAMPNO\n(MISSING)", "broken")
    G.add_edge(iid, "brk", label="hard key empty", style="broken")

# DTCs and first repair/part for P0300 or first mechanic code
shown_fix = 0
for code in dtcs:
    did = f"dtc:{code}"
    in_m = code in mech_codes
    addn(did, f"DTC {code}" + ("\n(in MechanicDB)" if in_m else "\n(not in sample)"), "dtc")
    G.add_edge("c", did, label="extracted", style="candidate")
    if "FUEL SYSTEM" in heads:
        G.add_edge("comp:FUEL SYSTEM", did, label="co-occur", style="candidate")
    if in_m and shown_fix < 2:
        fids = code_to_fix_ids.get(code) or []
        if fids:
            fid = fids[0]
            fx = fix_by_id.get(fid) or {}
            title = str(fx.get("fix_title") or fid)[:42]
            sid = f"fix:{fid}"
            addn(sid, f"RepairStep\n{title}", "step")
            G.add_edge(did, sid, label="forDtc", style="hard")
            pids = fix_to_parts.get(str(fid), []) or fix_to_parts.get(fid, [])
            if pids:
                pr = part_rows.get(str(pids[0])) or part_rows.get(pids[0]) or {}
                pname = str(pr.get("part_name") or pids[0])[:42]
                pidn = f"part:{pids[0]}"
                addn(pidn, f"Part\n{pname}", "part")
                G.add_edge(sid, pidn, label="usesPart", style="hard")
            shown_fix += 1

# layout: columns
cols = {
    "complaint": 0, "vehicle": 0,
    "component": 1, "investigation": 1,
    "recall": 2, "dtc": 2, "broken": 2,
    "step": 3,
    "part": 4,
}
bykind = defaultdict(list)
for n, d in G.nodes(data=True):
    bykind[d.get("kind", "x")].append(n)
pos = {}
for kind, nodes in bykind.items():
    x = cols.get(kind, 3)
    for i, n in enumerate(nodes):
        y = (len(nodes) - 1) / 2 - i
        # slight column offsets
        pos[n] = (x + (0.15 if kind == "investigation" else 0), y)

color = {
    "vehicle": "#4C78A8",
    "complaint": "#F58518",
    "component": "#54A24B",
    "recall": "#E45756",
    "investigation": "#B279A2",
    "dtc": "#72B7B2",
    "step": "#EECA3B",
    "part": "#9D755D",
    "broken": "#BBBBBB",
}

plt.figure(figsize=(16, 9), dpi=140)
ax = plt.gca()
ax.set_title(
    "Honda CR-V 2018 — longest trial chain (ODINO 11407338)\n"
    "Solid dark = hard edge; orange dashed = candidate; red dotted = official CAMPNO missing",
    fontsize=11,
)
nx.draw_networkx_nodes(
    G, pos,
    node_color=[color.get(G.nodes[n]["kind"], "#ccc") for n in G.nodes],
    node_size=2800, linewidths=0.6, edgecolors="#333",
    ax=ax,
)
labels = {n: G.nodes[n]["label"] for n in G.nodes}
nx.draw_networkx_labels(G, pos, labels=labels, font_size=6.5, ax=ax)

hard_e = [(u, v) for u, v, d in G.edges(data=True) if d.get("style") == "hard"]
cand_e = [(u, v) for u, v, d in G.edges(data=True) if d.get("style") == "candidate"]
brk_e = [(u, v) for u, v, d in G.edges(data=True) if d.get("style") == "broken"]
nx.draw_networkx_edges(G, pos, edgelist=hard_e, width=1.6, edge_color="#222", arrows=True, arrowsize=12, ax=ax, connectionstyle="arc3,rad=0.02")
nx.draw_networkx_edges(G, pos, edgelist=cand_e, width=1.2, edge_color="#F58518", style="dashed", arrows=True, arrowsize=12, ax=ax, connectionstyle="arc3,rad=0.08")
nx.draw_networkx_edges(G, pos, edgelist=brk_e, width=1.4, edge_color="#C00000", style="dotted", arrows=True, arrowsize=12, ax=ax, connectionstyle="arc3,rad=0.05")

elabs = {(u, v): d.get("label", "") for u, v, d in G.edges(data=True)}
nx.draw_networkx_edge_labels(G, pos, edge_labels=elabs, font_size=5.5, ax=ax, label_pos=0.45)

patches = [
    mpatches.Patch(color=color[k], label=k) for k in
    ("complaint", "vehicle", "component", "recall", "investigation", "dtc", "step", "part", "broken")
    if any(G.nodes[n]["kind"] == k for n in G.nodes)
]
ax.legend(handles=patches, loc="lower left", fontsize=7, framealpha=0.9)
ax.axis("off")
plt.tight_layout()
png_path = ROOT / "chain_odino_11407338.png"
plt.savefig(png_path, bbox_inches="tight", facecolor="white")
plt.close()
print("PNG", png_path, "nodes", G.number_of_nodes(), "edges", G.number_of_edges())
print("SPARQL written")
