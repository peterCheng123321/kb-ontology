#!/usr/bin/env python3
"""从 data/raw/ 公开数据可复现地构建第一阶段本田 CR-V / Accord 2018 试验切片。

输出到 data/honda-2018/（不进 git）：
  - slice_nhtsa_qa.json
  - mechanicdb.json
  - dtc_codeslist.json

严格隐私边界：
  - 不读取或写入 VIN（CMPL 字段 15）、城市/州、经销商、车辆操作人；
  - 投诉叙述（CMPL 字段 20）仅在内存中执行 DTC 正则提取，原文立即丢弃不落盘；
  - 中文问诊（vehicle_qa）原文/对话仅在内存中做部件词表匹配与 DTC 正则提取，
    只保留品牌/车型/部件主类与截断至 60 字的去标识短结论（report_short）。
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW = REPO_ROOT / "data" / "raw"
OUT = REPO_ROOT / "data" / "honda-2018"
LEXICON_PATH = REPO_ROOT / "src" / "mappings" / "zh_component_lexicon.yaml"
OUT.mkdir(parents=True, exist_ok=True)

TARGET_YEAR = "2018"
TARGET_MODELS = {"CR-V", "ACCORD"}
DTC_RE = re.compile(r"\b([PCBU][0-9A-Fa-f]{4})\b")

HEAD_ALIASES = {
    "FUEL": "FUEL SYSTEM",
    "FUEL/PROPULSION SYSTEM": "FUEL SYSTEM",
    "ENGINE AND ENGINE COOLING": "ENGINE",
}

MAKE_ALIASES = {
    "HONDA MOTOR": "HONDA",
    "HONDA (AMERICAN HONDA MOTOR CO.)": "HONDA",
    "VW": "VOLKSWAGEN",
    "CHEVY": "CHEVROLET",
}


def norm_space(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().upper())


def norm_make(s: str) -> str:
    m = norm_space(s)
    return MAKE_ALIASES.get(m, m)


def norm_model_group(s: str) -> str:
    m = norm_space(s)
    alnum = re.sub(r"[^A-Z0-9]", "", m)
    if alnum in {"CRV", "HONDACRV"} or m.startswith("CR-V") or m.startswith("CRV"):
        return "CR-V"
    if alnum in {"ACCORD", "ACCORDHYBRID", "ACCORDHEV"} or m.startswith("ACCORD"):
        return "ACCORD"
    return m


def extract_comp_head(comp_desc: str) -> str:
    raw = norm_space(comp_desc)
    if not raw:
        return ""
    head = raw.split(":")[0].strip()
    if "," in head:
        head = head.split(",")[0].strip()
    return HEAD_ALIASES.get(head, head)


def extract_dtcs(text: str) -> list[str]:
    if not text:
        return []
    found = []
    for m in DTC_RE.findall(text):
        c = m.upper()
        # Exclude obvious false positives like C2018 / P2020 year-like tokens? Keep exact Phase 1 regex semantics.
        if c not in found:
            found.append(c)
    return found


def iter_zip_tsv(zip_path: Path):
    with zipfile.ZipFile(zip_path) as zf:
        txt_names = [n for n in zf.namelist() if n.lower().endswith(".txt")]
        name = txt_names[0] if txt_names else zf.namelist()[0]
        with zf.open(name) as fh:
            wrapper = io.TextIOWrapper(fh, encoding="latin-1", newline="")
            for line in wrapper:
                yield line.rstrip("\r\n").split("\t")


def load_zh_lexicon() -> dict[str, list[str]]:
    data = yaml.safe_load(LEXICON_PATH.read_text(encoding="utf-8"))
    out: dict[str, list[str]] = {}
    for head, cfg in (data.get("heads") or {}).items():
        kws = [str(k).strip() for k in (cfg.get("keywords") or []) if str(k).strip()]
        out[head] = kws
    return out


def match_zh_components(text: str, lexicon: dict[str, list[str]]) -> list[str]:
    if not text:
        return []
    low = text.lower()
    hits = []
    for head, kws in lexicon.items():
        if any(k.lower() in low for k in kws):
            hits.append(head)
    return sorted(hits)


def build_complaints() -> list[dict]:
    cmpl_zips = [
        RAW / "COMPLAINTS_RECEIVED_2020-2024.zip",
        RAW / "COMPLAINTS_RECEIVED_2025-2026.zip",
    ]
    missing = [str(p) for p in cmpl_zips if not p.exists()]
    if missing:
        flat = RAW / "FLAT_CMPL.zip"
        if flat.exists():
            cmpl_zips = [flat]
        else:
            raise FileNotFoundError(f"Missing complaint zips: {missing}")

    rows = []
    seen_cmplid = set()
    for zp in cmpl_zips:
        for cols in iter_zip_tsv(zp):
            if len(cols) < 20:
                continue
            cmplid = cols[0].strip()
            odino = cols[1].strip()
            make = norm_make(cols[3])
            model = norm_model_group(cols[4])
            year = cols[5].strip()
            if year == "9999" or make != "HONDA" or model not in TARGET_MODELS or year != TARGET_YEAR:
                continue
            if cmplid and cmplid in seen_cmplid:
                continue
            seen_cmplid.add(cmplid)

            crash = cols[6].strip().upper()
            fire = cols[8].strip().upper()
            comp_desc = norm_space(cols[11])
            comp_head = extract_comp_head(comp_desc)
            received_date = cols[16].strip()
            # Field 20 (index 19): CDESCR — ONLY regex-extract DTCs in memory, NEVER store text
            dtcs = extract_dtcs(cols[19])

            rows.append({
                "cmplid": cmplid,
                "odino": odino,
                "make": "HONDA",
                "model": model,
                "year": TARGET_YEAR,
                "comp_head": comp_head,
                "comp_desc": comp_desc,
                "dtcs": dtcs,
                "received_date": received_date,
                "crash": crash,
                "fire": fire,
            })
    return rows


def build_recalls() -> list[dict]:
    rcl_zip = RAW / "FLAT_RCL_POST_2010.zip"
    if not rcl_zip.exists():
        raise FileNotFoundError(f"Missing {rcl_zip}")
    rows = []
    for cols in iter_zip_tsv(rcl_zip):
        if len(cols) < 22:
            continue
        campno = cols[1].strip().upper()
        make = norm_make(cols[2])
        model = norm_model_group(cols[3])
        year = cols[4].strip()
        if year == "9999" or make != "HONDA" or model not in TARGET_MODELS or year != TARGET_YEAR:
            continue
        mfr_campno = cols[5].strip()
        comp_desc = norm_space(cols[6])
        comp_head = extract_comp_head(comp_desc)
        potaff = cols[11].strip()
        rcdate = cols[15].strip() if len(cols) > 15 else ""
        defect_summary = cols[19].strip()
        corrective_action = cols[21].strip()
        rows.append({
            "campno": campno,
            "make": "HONDA",
            "model": model,
            "year": TARGET_YEAR,
            "mfr_campno": mfr_campno,
            "comp_head": comp_head,
            "comp_desc": comp_desc,
            "potaff": potaff,
            "rcdate": rcdate,
            "defect_summary": defect_summary,
            "corrective_action": corrective_action,
        })
    return rows


def build_investigations() -> list[dict]:
    inv_zip = RAW / "FLAT_INV.zip"
    if not inv_zip.exists():
        raise FileNotFoundError(f"Missing {inv_zip}")
    rows = []
    for cols in iter_zip_tsv(inv_zip):
        if len(cols) < 11:
            continue
        action_number = cols[0].strip().upper()
        make = norm_make(cols[1])
        model = norm_model_group(cols[2])
        year = cols[3].strip()
        if year == "9999" or make != "HONDA" or model not in TARGET_MODELS or year != TARGET_YEAR:
            continue
        comp_desc = norm_space(cols[4])
        comp_head = extract_comp_head(comp_desc)
        campno = cols[8].strip().upper()
        subject = cols[9].strip()
        summary = cols[10].strip()
        rows.append({
            "action_number": action_number,
            "campno": campno,
            "make": "HONDA",
            "model": model,
            "year": TARGET_YEAR,
            "comp_head": comp_head,
            "comp_desc": comp_desc,
            "subject": subject,
            "summary": summary,
        })
    return rows


def build_qa(lexicon: dict[str, list[str]]) -> list[dict]:
    qa_dir = RAW / "hf" / "vehicle_qa"
    rows = []
    seen_qid = set()
    for fn in ("train.csv", "test.csv"):
        p = qa_dir / fn
        if not p.exists():
            continue
        with p.open(encoding="utf-8", errors="replace", newline="") as fh:
            rd = csv.DictReader(fh)
            for r in rd:
                qid = (r.get("QID") or "").strip()
                brand = (r.get("Brand") or "").strip()
                model = (r.get("Model") or "").strip()
                if "本田" not in brand and "本田" not in model and "雅阁" not in model:
                    continue
                m_up = model.upper()
                if "CR-V" in m_up or "CRV" in m_up:
                    model_mapped = "CR-V"
                elif "雅阁" in model or "ACCORD" in m_up:
                    model_mapped = "ACCORD"
                else:
                    continue
                if qid and qid in seen_qid:
                    continue
                seen_qid.add(qid)

                q_txt = (r.get("Question") or "").strip()
                d_txt = (r.get("Dialogue") or "").strip()
                rep = (r.get("Report") or "").strip()
                blob = " ".join([q_txt, d_txt, rep])
                comp_heads = match_zh_components(blob, lexicon)
                dtcs = extract_dtcs(blob)
                # Keep only short de-identified conclusion (<= 60 chars), never raw dialogue
                rep_clean = re.sub(r"\s+", " ", rep)
                rep_clean = re.sub(r"1[3-9]\d{9}", "[PHONE]", rep_clean)
                report_short = rep_clean[:60]

                rows.append({
                    "qid": qid,
                    "brand_raw": brand,
                    "model_raw": model,
                    "make_mapped": "HONDA",
                    "model_mapped": model_mapped,
                    "comp_heads": comp_heads,
                    "report_short": report_short,
                    "dtcs": dtcs,
                })
    return rows


def build_mechanicdb() -> dict:
    mdir = RAW / "hf" / "mechanicdb"
    def read_pq(name: str) -> list[dict]:
        p = mdir / name
        if not p.exists():
            raise FileNotFoundError(f"Missing {p}")
        tbl = pq.read_table(p)
        recs = []
        for row in tbl.to_pylist():
            clean = {k: v for k, v in row.items() if k != "__index_level_0__"}
            recs.append(clean)
        return recs

    return {
        "dtc_codes": read_pq("dtc_codes.parquet"),
        "fixes": read_pq("diagnostic_fixes.parquet"),
        "joined": read_pq("dtc_fixes_joined.parquet"),
        "parts": read_pq("replacement_parts.parquet"),
    }


def build_codeslist() -> list[dict]:
    p = RAW / "obd2-codes.csv"
    if not p.exists():
        raise FileNotFoundError(f"Missing {p}")
    rows = []
    with p.open(encoding="utf-8", errors="replace", newline="") as fh:
        rd = csv.DictReader(fh)
        for r in rd:
            # Handle case-insensitive column names (Code/code, Description/description, Category/category)
            low = {k.strip().lower(): (v or "").strip() for k, v in r.items() if k}
            code = low.get("code", "").upper()
            if not code:
                continue
            rows.append({
                "code": code,
                "description": low.get("description", ""),
                "category": low.get("category", ""),
            })
    return rows


def main() -> int:
    lexicon = load_zh_lexicon()
    complaints = build_complaints()
    recalls = build_recalls()
    investigations = build_investigations()
    qa = build_qa(lexicon)
    mech = build_mechanicdb()
    codes = build_codeslist()

    slice_obj = {
        "complaints": complaints,
        "recalls": recalls,
        "investigations": investigations,
        "qa": qa,
    }
    (OUT / "slice_nhtsa_qa.json").write_text(json.dumps(slice_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "mechanicdb.json").write_text(json.dumps(mech, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "dtc_codeslist.json").write_text(json.dumps(codes, ensure_ascii=False, indent=2), encoding="utf-8")

    odinos = {r["odino"] for r in complaints}
    camps = {r["campno"] for r in recalls}
    acts = {r["action_number"] for r in investigations}
    dtcs = {d for r in complaints for d in r["dtcs"]} | {d for r in qa for d in r["dtcs"]}
    qa_models = Counter(r["model_mapped"] for r in qa)
    print(f"Wrote {OUT}/slice_nhtsa_qa.json")
    print(f"  complaints: {len(complaints)} rows / {len(odinos)} distinct ODINO")
    print(f"  recalls: {len(recalls)} rows / {len(camps)} distinct CAMPNO -> {sorted(camps)}")
    print(f"  investigations: {len(investigations)} rows / {len(acts)} distinct ACTION -> {sorted(acts)}")
    print(f"  qa: {len(qa)} threads {dict(qa_models)}")
    print(f"  extracted DTCs in slice: {len(dtcs)}")
    print(f"  mechanicdb: codes={len(mech['dtc_codes'])}, fixes={len(mech['fixes'])}, joined={len(mech['joined'])}, parts={len(mech['parts'])}")
    print(f"  codeslist: {len(codes)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
