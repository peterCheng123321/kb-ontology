#!/usr/bin/env python3
"""跨平台扩展数据源下载与双轨连接度探查脚本（仅使用 Python 标准库，兼容 Python 3.9+）。

功能：
1. 加 --fetch 将免登录、许可证清晰的 A 级扩展数据源及轻量基线拉取到本地 data/raw/（不入 Git）。
2. 执行双轨探查计算（无 VIN、无 PII、无原始长文本），产出 docs/stats/extended-probe-stats.json：
   - 轨 1（全球车型与通用诊断）：
     * Transport Canada 召回库 vs NHTSA 召回与本田 2018 切片（厂内活动号硬键 & 部件对齐）
     * 英国 DVSA MOT 年检字典（Class 4 乘用车缺陷层级树、新能源燃料枚举 & NHTSA 部件大类映射）
     * 开源 DTC 扩展（Wal33D MIT 通用+33厂标库、OBDex CC0 审校库 vs CodesList 与 NHTSA 抽出码）
     * 行业标准信号与 CAN 总线（COVESA VSS v6.1、W3C VSSo、commaai/opendbc 本田/比亚迪/特斯拉 DBC）
   - 轨 2（新能源三电与结构化维修扩展参考）：
     * Figshare & Zenodo (via DataCite) CC-BY-4.0 新能源 BMS 故障诊断与结构化维修库元数据汇总
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sqlite3
import ssl
import sys
import urllib.error
import urllib.request
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw"
EXT_DIR = RAW_DIR / "extended"
JOIN_STATS_PATH = REPO_ROOT / "docs" / "stats" / "join-stats.json"
OUT_STATS_PATH = REPO_ROOT / "docs" / "stats" / "extended-probe-stats.json"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
SSL_CTX = ssl.create_default_context()

# 免登录直链 A 级扩展源与轻量对照基线
FETCH_TARGETS = {
    "nhtsa_rcl_post2010": {
        "url": "https://static.nhtsa.gov/odi/ffdd/rcl/FLAT_RCL_POST_2010.zip",
        "dest": RAW_DIR / "FLAT_RCL_POST_2010.zip",
        "license": "Public Domain (U.S. Government)",
    },
    "codeslist_obd2_csv": {
        "url": "https://huggingface.co/datasets/CodesList/obd2-codes/resolve/main/obd2-codes.csv",
        "dest": RAW_DIR / "obd2-codes.csv",
        "license": "CC-BY-4.0",
    },
    "tc_vrdb_csv": {
        "url": "https://opendatatc.tc.canada.ca/vrdb_full_monthly.csv",
        "dest": EXT_DIR / "vrdb_full_monthly.csv",
        "license": "Open Government Licence - Canada",
    },
    "uk_mot_lookup": {
        "url": "https://data.dft.gov.uk/anonymised-mot-test/lookup.zip",
        "dest": EXT_DIR / "uk_mot_lookup.zip",
        "license": "UK Open Government Licence (OGL)",
    },
    "wal33d_dtc_db": {
        "url": "https://raw.githubusercontent.com/Wal33D/dtc-database/main/data/dtc_codes.db",
        "dest": EXT_DIR / "wal33d_dtc_codes.db",
        "license": "MIT",
    },
    "covesa_vss_csv": {
        "url": "https://github.com/COVESA/vehicle_signal_specification/releases/download/v6.1/vss.csv",
        "dest": EXT_DIR / "covesa_vss_v6.1.csv",
        "license": "MPL-2.0",
    },
    "w3c_vsso_core_ttl": {
        "url": "https://raw.githubusercontent.com/w3c/vsso/gh-pages/spec/vsso-core.ttl",
        "dest": EXT_DIR / "w3c_vsso" / "vsso-core.ttl",
        "license": "CC-BY-4.0",
    },
    "w3c_vsso_vss22_ttl": {
        "url": "https://raw.githubusercontent.com/w3c/vsso/gh-pages/spec/vss_rel_2.2.ttl",
        "dest": EXT_DIR / "w3c_vsso" / "vss_rel_2.2.ttl",
        "license": "CC-BY-4.0",
    },
}

OBDEX_FILES = [
    "data/generic/B0xxx_enriched.yaml",
    "data/generic/C0xxx_enriched.yaml",
    "data/generic/P0xxx_enriched.yaml",
    "data/generic/P2xxx_enriched.yaml",
    "data/generic/P3xxx_enriched.yaml",
    "data/generic/U0xxx_enriched.yaml",
    "data/generic/U3xxx_enriched.yaml",
    "data/pids/mode01.yaml",
    "data/pids/mode09.yaml",
]

OPENDBC_FILES = [
    "opendbc/dbc/generator/honda/_bosch_2018.dbc",
    "opendbc/dbc/generator/honda/_bosch_radar_acc.dbc",
    "opendbc/dbc/generator/honda/_honda_common.dbc",
    "opendbc/dbc/generator/honda/honda_crv_ex_2017_body.dbc",
    "opendbc/dbc/generator/honda/honda_clarity_hybrid_2018_can.dbc",
    "opendbc/dbc/byd_atto3.dbc",
    "opendbc/dbc/tesla_model3_vehicle.dbc",
    "opendbc/dbc/tesla_powertrain.dbc",
]

FIGSHARE_IDS = [23659323, 30162841, 23301881]
DATACITE_DOIS = [
    "10.5281/zenodo.19006180",
    "10.5281/zenodo.10656500",
    "10.5281/zenodo.18328700",
    "10.5281/zenodo.15626055",
]

RANGE_PROBE_URLS = {
    "uk_mot_result_2023": "https://data.dft.gov.uk/anonymised-mot-test/test_data/dft_test_result_2023.zip",
    "uk_mot_item_2023": "https://data.dft.gov.uk/anonymised-mot-test/test_data/dft_test_item_2023.zip",
}


def download_file(url: str, dest: Path, timeout: int = 120) -> dict[str, Any]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return {"url": url, "dest": str(dest.relative_to(REPO_ROOT)), "bytes": dest.stat().st_size, "cached": True, "status": 200}
    req = urllib.request.Request(url, headers={"User-Agent": UA}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
        status = resp.status
        final_url = resp.geturl()
        tmp = dest.with_suffix(dest.suffix + ".part")
        total = 0
        with tmp.open("wb") as fh:
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                fh.write(chunk)
                total += len(chunk)
        tmp.replace(dest)
    return {"url": url, "final_url": final_url, "dest": str(dest.relative_to(REPO_ROOT)), "bytes": total, "cached": False, "status": status}


def fetch_json_url(url: str, timeout: int = 15) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def range_probe(url: str, timeout: int = 15) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Range": "bytes=0-63"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
            resp.read(64)
            return {
                "url": url,
                "status": resp.status,
                "content_length": resp.headers.get("Content-Length"),
                "content_range": resp.headers.get("Content-Range"),
                "last_modified": resp.headers.get("Last-Modified"),
            }
    except urllib.error.HTTPError as e:
        return {"url": url, "status": e.code, "error": str(e)}
    except Exception as e:
        return {"url": url, "status": None, "error": str(e)}


def fetch_all() -> dict[str, Any]:
    endpoints = []
    for key, spec in FETCH_TARGETS.items():
        print(f"[fetch] {key} <- {spec['url']}", flush=True)
        try:
            res = download_file(spec["url"], spec["dest"])
            res["key"] = key
            res["license"] = spec["license"]
            endpoints.append(res)
            print(f"  ok bytes={res['bytes']} cached={res['cached']}", flush=True)
        except Exception as e:
            print(f"  ERR {e}", flush=True)
            endpoints.append({"key": key, "url": spec["url"], "error": str(e)})

    for rel_path in OBDEX_FILES:
        url = f"https://raw.githubusercontent.com/foerbsnavi/OBDex/main/{rel_path}"
        dest = EXT_DIR / "obdex" / rel_path
        print(f"[fetch] obdex:{rel_path}", flush=True)
        try:
            res = download_file(url, dest, timeout=30)
            res["key"] = f"obdex:{rel_path}"
            res["license"] = "CC0-1.0"
            endpoints.append(res)
        except Exception as e:
            endpoints.append({"key": f"obdex:{rel_path}", "url": url, "error": str(e)})

    for rel_path in OPENDBC_FILES:
        url = f"https://raw.githubusercontent.com/commaai/opendbc/master/{rel_path}"
        dest = EXT_DIR / "opendbc" / Path(rel_path).name
        print(f"[fetch] opendbc:{Path(rel_path).name}", flush=True)
        try:
            res = download_file(url, dest, timeout=30)
            res["key"] = f"opendbc:{Path(rel_path).name}"
            res["license"] = "MIT"
            endpoints.append(res)
        except Exception as e:
            endpoints.append({"key": f"opendbc:{Path(rel_path).name}", "url": url, "error": str(e)})

    for name, url in RANGE_PROBE_URLS.items():
        print(f"[probe] {name}", flush=True)
        r = range_probe(url)
        r["key"] = f"probe:{name}"
        endpoints.append(r)

    academic: dict[str, Any] = {"figshare": [], "datacite_zenodo": []}
    for fid in FIGSHARE_IDS:
        print(f"[api] figshare:{fid}", flush=True)
        try:
            j = fetch_json_url(f"https://api.figshare.com/v2/articles/{fid}")
            academic["figshare"].append({
                "id": j.get("id"),
                "doi": j.get("doi"),
                "title": j.get("title"),
                "url": j.get("url_public_html"),
                "license": (j.get("license") or {}).get("name"),
                "published_date": j.get("published_date"),
                "total_bytes": j.get("size"),
                "files": [{"name": f.get("name"), "size": f.get("size")} for f in j.get("files", [])],
            })
        except Exception as e:
            academic["figshare"].append({"id": fid, "error": str(e)})

    for doi in DATACITE_DOIS:
        print(f"[api] datacite:{doi}", flush=True)
        try:
            j = fetch_json_url(f"https://api.datacite.org/dois/{doi}")
            attr = j.get("data", {}).get("attributes", {})
            titles = attr.get("titles") or []
            rights = attr.get("rightsList") or []
            academic["datacite_zenodo"].append({
                "doi": doi,
                "url": attr.get("url"),
                "title": titles[0].get("title") if titles else None,
                "publication_year": attr.get("publicationYear"),
                "licenses": sorted({r.get("rightsIdentifier") or r.get("rights") for r in rights if r.get("rightsIdentifier") or r.get("rights")}),
                "publisher": attr.get("publisher"),
            })
        except Exception as e:
            academic["datacite_zenodo"].append({"doi": doi, "error": str(e)})

    (EXT_DIR / "academic_metadata.json").write_text(json.dumps(academic, ensure_ascii=False, indent=2))
    (EXT_DIR / "fetch_manifest.json").write_text(json.dumps(endpoints, ensure_ascii=False, indent=2))
    return {"endpoints": endpoints, "academic": academic}


def norm_space(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().upper())


def norm_alnum(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", norm_space(s))


def norm_year(y: str) -> str:
    s = (y or "").strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def tokenize_mfr_recall(s: str) -> list[str]:
    out = []
    for part in re.split(r"[,;/]|\bAND\b", s or "", flags=re.I):
        t = norm_space(part).strip(" .")
        if not t or t in {"MULTIPLE CODES", "REFER TO COMMENTS", "N/A", "NONE", "UNKNOWN"}:
            continue
        if len(t) >= 2 and t not in out:
            out.append(t)
    return out


def norm_make(s: str) -> str:
    m = norm_space(s)
    aliases = {
        "HONDA MOTOR": "HONDA",
        "HONDA CANADA INC.": "HONDA",
        "HONDA (AMERICAN HONDA MOTOR CO.)": "HONDA",
        "VW": "VOLKSWAGEN",
        "CHEVY": "CHEVROLET",
        "MERCEDES BENZ": "MERCEDES-BENZ",
    }
    return aliases.get(m, m)


def norm_model_group(s: str) -> str:
    a = norm_alnum(s)
    if a in {"CRV", "HONDACRV"}:
        return "CR-V"
    if a in {"ACCORD", "ACCORDHYBRID", "ACCORDHEV"}:
        return "ACCORD"
    return norm_space(s)


def analyze_transport_canada_vs_nhtsa() -> dict[str, Any]:
    tc_csv = EXT_DIR / "vrdb_full_monthly.csv"
    nhtsa_zip = RAW_DIR / "FLAT_RCL_POST_2010.zip"
    if not tc_csv.exists() or not nhtsa_zip.exists():
        return {"error": "Missing vrdb_full_monthly.csv or FLAT_RCL_POST_2010.zip; run with --fetch first."}

    # 1. Parse NHTSA FLAT_RCL_POST_2010.zip
    nhtsa_mfr_tokens: set[str] = set()
    nhtsa_mfr_to_camps: dict[str, set[str]] = defaultdict(set)
    nhtsa_honda_2018_mfr_to_camps: dict[str, set[str]] = defaultdict(set)
    nhtsa_honda_2018_camps: set[str] = set()
    nhtsa_comp_heads: set[str] = set()
    nhtsa_mmy_set: set[tuple[str, str, str]] = set()
    nhtsa_rows = 0

    with zipfile.ZipFile(nhtsa_zip) as z:
        fname = z.namelist()[0]
        with z.open(fname) as fh:
            for line in io.TextIOWrapper(fh, encoding="latin-1", newline=""):
                p = line.rstrip("\n\r").split("\t")
                if len(p) < 7:
                    continue
                nhtsa_rows += 1
                campno = (p[1] or "").strip().upper()
                make = norm_make(p[2])
                model = norm_space(p[3])
                year = norm_year(p[4])
                mfr_raw = (p[5] or "").strip()
                comp = norm_space(p[6])
                if make and model and year and year != "9999":
                    nhtsa_mmy_set.add((make, norm_alnum(model), year))
                if comp:
                    nhtsa_comp_heads.add(comp.split(":")[0].strip())
                tokens = tokenize_mfr_recall(mfr_raw)
                for t in tokens:
                    nhtsa_mfr_tokens.add(t)
                    if campno:
                        nhtsa_mfr_to_camps[t].add(campno)
                if make == "HONDA" and year == "2018" and norm_model_group(model) in {"CR-V", "ACCORD"}:
                    if campno:
                        nhtsa_honda_2018_camps.add(campno)
                    for t in tokens:
                        if campno:
                            nhtsa_honda_2018_mfr_to_camps[t].add(campno)

    # 2. Parse Transport Canada vrdb_full_monthly.csv
    tc_rows = 0
    tc_cols: list[str] = []
    tc_col_nonempty: Counter[str] = Counter()
    tc_recall_nums: set[str] = set()
    tc_mfr_tokens: set[str] = set()
    tc_mfr_to_recalls: dict[str, set[str]] = defaultdict(set)
    tc_sys_types: Counter[str] = Counter()
    tc_categories: Counter[str] = Counter()
    tc_mmy_set: set[tuple[str, str, str]] = set()
    tc_honda_2018_rows = 0
    tc_honda_2018_recalls: dict[str, dict[str, Any]] = {}

    with tc_csv.open("r", encoding="utf-8-sig", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        tc_cols = list(reader.fieldnames or [])
        for row in reader:
            tc_rows += 1
            for c in tc_cols:
                if (row.get(c) or "").strip():
                    tc_col_nonempty[c] += 1
            rnum = (row.get("RECALL_NUMBER_NUM") or "").strip()
            if rnum:
                tc_recall_nums.add(rnum)
            make = norm_make(row.get("MAKE_NAME_NM") or "")
            model = norm_space(row.get("MODEL_NAME_NM") or "")
            year = norm_year(row.get("YEAR") or "")
            if make and model and year:
                tc_mmy_set.add((make, norm_alnum(model), year))
            sys_t = norm_space(row.get("SYSTEM_TYPE_ETXT") or "")
            if sys_t:
                tc_sys_types[sys_t] += 1
            cat_t = norm_space(row.get("CATEGORY_ETXT") or "")
            if cat_t:
                tc_categories[cat_t] += 1
            mfr_raw = (row.get("MANUFACTURER_RECALL_NO_TXT") or "").strip()
            tokens = tokenize_mfr_recall(mfr_raw)
            for t in tokens:
                tc_mfr_tokens.add(t)
                if rnum:
                    tc_mfr_to_recalls[t].add(rnum)

            if make == "HONDA" and year == "2018" and norm_model_group(model) in {"CR-V", "ACCORD"}:
                tc_honda_2018_rows += 1
                rec = tc_honda_2018_recalls.setdefault(rnum, {
                    "tc_recall_number": rnum,
                    "models": set(),
                    "mfr_tokens": set(),
                    "system_types": set(),
                    "recall_date": (row.get("RECALL_DATE_DTE") or "").strip(),
                    "unit_affected": (row.get("UNIT_AFFECTED_NBR") or "").strip(),
                })
                rec["models"].add(norm_model_group(model))
                rec["mfr_tokens"].update(tokens)
                if sys_t:
                    rec["system_types"].add(sys_t)

    shared_mfr_tokens = tc_mfr_tokens & nhtsa_mfr_tokens
    tc_recalls_linked_to_nhtsa = set()
    nhtsa_camps_linked_to_tc = set()
    for t in shared_mfr_tokens:
        tc_recalls_linked_to_nhtsa.update(tc_mfr_to_recalls[t])
        nhtsa_camps_linked_to_tc.update(nhtsa_mfr_to_camps[t])

    honda_2018_hard_matches = []
    matched_nhtsa_honda_camps = set()
    for rnum, rec in sorted(tc_honda_2018_recalls.items()):
        hit_camps: set[str] = set()
        hit_tokens: list[str] = []
        for t in sorted(rec["mfr_tokens"]):
            if t in nhtsa_honda_2018_mfr_to_camps:
                hit_camps.update(nhtsa_honda_2018_mfr_to_camps[t])
                hit_tokens.append(t)
        matched_nhtsa_honda_camps.update(hit_camps)
        honda_2018_hard_matches.append({
            "tc_recall_number": rnum,
            "models": sorted(rec["models"]),
            "mfr_tokens": sorted(rec["mfr_tokens"]),
            "system_types": sorted(rec["system_types"]),
            "recall_date": rec["recall_date"],
            "matched_nhtsa_campnos": sorted(hit_camps),
            "matched_via_tokens": hit_tokens,
        })

    # TC system_type -> NHTSA head mapping
    tc_to_nhtsa_head = {
        "ELECTRICAL": "ELECTRICAL SYSTEM",
        "AIR BAGS": "AIR BAGS",
        "BRAKES": "SERVICE BRAKES",
        "SERVICE BRAKES, HYDRAULIC": "SERVICE BRAKES",
        "FUEL SUPPLY": "FUEL SYSTEM",
        "FUEL SYSTEM": "FUEL SYSTEM",
        "POWERTRAIN": "POWER TRAIN",
        "POWER TRAIN": "POWER TRAIN",
        "STEERING": "STEERING",
        "SUSPENSION": "SUSPENSION",
        "SEAT BELTS AND AIR BAGS": "SEAT BELTS",
        "SEAT BELTS": "SEAT BELTS",
        "STRUCTURE": "STRUCTURE",
        "LIGHTS AND INSTRUMENTS": "EXTERIOR LIGHTING",
        "EXTERIOR LIGHTING": "EXTERIOR LIGHTING",
        "VISIBILITY": "VISIBILITY",
        "TIRES": "TIRES",
        "WHEELS": "WHEELS",
        "ENGINE": "ENGINE AND ENGINE COOLING",
        "ENGINE AND ENGINE COOLING": "ENGINE AND ENGINE COOLING",
        "EQUIPMENT": "EQUIPMENT",
        "SEATS": "SEATS",
        "SEATS AND RESTRAINTS": "SEATS",
        "VEHICLE SPEED CONTROL": "VEHICLE SPEED CONTROL",
        "LATCHES/LOCKS/LINKAGES": "LATCHES/LOCKS/LINKAGES",
        "FORWARD COLLISION AVOIDANCE": "FORWARD COLLISION AVOIDANCE",
        "BACK OVER PREVENTION": "BACK OVER PREVENTION",
        "TRAILER HITCHES": "TRAILER HITCHES",
        "CHILD SEAT": "CHILD SEAT",
        "PARKING BRAKE": "PARKING BRAKE",
        "HYBRID PROPULSION SYSTEM": "HYBRID PROPULSION SYSTEM",
        "COMMUNICATION": "COMMUNICATION",
        "ACCESSORIES": "EQUIPMENT",
        "WHEELS AND TIRES": "TIRES",
    }
    sys_mapped_rows = sum(cnt for k, cnt in tc_sys_types.items() if k in tc_to_nhtsa_head or k in nhtsa_comp_heads)

    return {
        "tc_total_rows": tc_rows,
        "tc_columns": tc_cols,
        "tc_column_fill_rates": {c: round(tc_col_nonempty[c] / max(tc_rows, 1), 4) for c in tc_cols},
        "tc_distinct_recall_numbers": len(tc_recall_nums),
        "tc_distinct_mfr_tokens": len(tc_mfr_tokens),
        "tc_distinct_mmy": len(tc_mmy_set),
        "tc_top_categories": dict(tc_categories.most_common(8)),
        "tc_top_system_types": dict(tc_sys_types.most_common(20)),
        "tc_system_type_nhtsa_head_coverage_pct": round(100.0 * sys_mapped_rows / max(sum(tc_sys_types.values()), 1), 2),
        "nhtsa_post2010_rows": nhtsa_rows,
        "nhtsa_distinct_mfr_tokens": len(nhtsa_mfr_tokens),
        "cross_border_global_joins": {
            "shared_mmy_count": len(tc_mmy_set & nhtsa_mmy_set),
            "shared_mfr_recall_tokens": len(shared_mfr_tokens),
            "tc_recalls_linked_to_nhtsa_post2010": len(tc_recalls_linked_to_nhtsa),
            "tc_recalls_linked_pct": round(100.0 * len(tc_recalls_linked_to_nhtsa) / max(len(tc_recall_nums), 1), 2),
            "nhtsa_post2010_camps_linked_to_tc": len(nhtsa_camps_linked_to_tc),
        },
        "honda_2018_slice_cross_border": {
            "tc_rows": tc_honda_2018_rows,
            "tc_distinct_recalls": len(tc_honda_2018_recalls),
            "nhtsa_distinct_camps_in_slice": len(nhtsa_honda_2018_camps),
            "nhtsa_camps_matched_via_mfr_no_to_tc": sorted(matched_nhtsa_honda_camps),
            "nhtsa_camps_matched_count": len(matched_nhtsa_honda_camps),
            "tc_recalls_detail": honda_2018_hard_matches,
        },
    }


def analyze_uk_mot_lookup() -> dict[str, Any]:
    lzip = EXT_DIR / "uk_mot_lookup.zip"
    if not lzip.exists():
        return {"error": "Missing uk_mot_lookup.zip; run with --fetch first."}

    files_summary = {}
    item_groups: list[dict[str, str]] = []
    item_details: list[dict[str, str]] = []
    fuel_types: list[dict[str, str]] = []
    test_outcomes: list[dict[str, str]] = []
    test_types: list[dict[str, str]] = []
    rfr_locations_count = 0

    with zipfile.ZipFile(lzip) as z:
        for name in sorted(z.namelist()):
            if name.endswith("/"):
                continue
            raw_text = z.read(name).decode("utf-8", errors="replace")
            lines = raw_text.splitlines()
            if not lines:
                continue
            delim = "|" if "|" in lines[0] else ("," if "," in lines[0] else "\t")
            reader = csv.DictReader(io.StringIO(raw_text), delimiter=delim)
            rows = list(reader)
            cols = list(reader.fieldnames or [])
            files_summary[name] = {"rows": len(rows), "cols": cols, "delimiter": delim}
            low = name.lower()
            if "item_group" in low:
                item_groups = rows
            elif "item_detail" in low:
                item_details = rows
            elif "fuel" in low:
                fuel_types = rows
            elif "outcome" in low:
                test_outcomes = rows
            elif "test_type" in low:
                test_types = rows
            elif "rfr_location" in low:
                rfr_locations_count = len(rows)

    # Analyze Class 4 (passenger cars) taxonomy tree in item_group.csv
    class4_nodes = {r["test_item_id"]: r for r in item_groups if (r.get("test_class_id") or "").strip() == "4"}
    children_map: dict[str, list[str]] = defaultdict(list)
    for nid, r in class4_nodes.items():
        pid = (r.get("parent_id") or "").strip()
        if nid != pid:
            children_map[pid].append(nid)

    # Top-level branches under root '0'
    top_branches_c4 = [class4_nodes[cid] for cid in children_map.get("0", []) if cid in class4_nodes]

    # Compute tree depth via BFS
    max_depth = 0
    q = [("0", 0)]
    seen = {"0"}
    while q:
        cur, d = q.pop(0)
        if d > max_depth:
            max_depth = d
        for ch in children_map.get(cur, []):
            if ch not in seen:
                seen.add(ch)
                q.append((ch, d + 1))

    class4_rfrs = [r for r in item_details if (r.get("test_class_id") or "").strip() == "4"]
    def_cat_dist = Counter((r.get("rfr_deficiency_category") or "").strip() or "(empty)" for r in class4_rfrs)

    mot_to_nhtsa = {
        "BRAKE": "SERVICE BRAKES",
        "TYRE": "TIRES",
        "TIRE": "TIRES",
        "SUSPENSION": "SUSPENSION",
        "STEERING": "STEERING",
        "LAMP": "EXTERIOR LIGHTING",
        "LIGHT": "EXTERIOR LIGHTING",
        "REFLECTOR": "EXTERIOR LIGHTING",
        "ELECTRICAL": "ELECTRICAL SYSTEM",
        "SEAT BELT": "SEAT BELTS",
        "RESTRAINT": "AIR BAGS",
        "SUPPLEMENTARY": "AIR BAGS",
        "SRS": "AIR BAGS",
        "EXHAUST": "ENGINE AND ENGINE COOLING",
        "EMISSION": "ENGINE AND ENGINE COOLING",
        "NOISE": "ENGINE AND ENGINE COOLING",
        "FUEL": "FUEL SYSTEM",
        "WINDSCREEN": "VISIBILITY",
        "WIPER": "VISIBILITY",
        "WASHER": "VISIBILITY",
        "MIRROR": "VISIBILITY",
        "VIEW": "VISIBILITY",
        "BODY": "STRUCTURE",
        "CHASSIS": "STRUCTURE",
        "STRUCTURE": "STRUCTURE",
        "TOWING": "TRAILER HITCHES",
        "SPEEDOMETER": "VEHICLE SPEED CONTROL",
        "SPEED LIMITER": "VEHICLE SPEED CONTROL",
        "WHEEL": "WHEELS",
        "HORN": "EQUIPMENT",
        "REGISTRATION PLATE": "EQUIPMENT",
        "IDENTIFICATION": "EQUIPMENT",
        "DOOR": "LATCHES/LOCKS/LINKAGES",
        "SEAT": "SEATS",
    }

    mapped_top = []
    unmapped_top = []
    for node in top_branches_c4:
        nm = (node.get("item_name") or "").strip()
        up = nm.upper()
        matched = None
        for kw, head in mot_to_nhtsa.items():
            if kw in up:
                matched = head
                break
        if matched:
            mapped_top.append({"mot_top_group": nm, "nhtsa_head": matched})
        else:
            unmapped_top.append(nm)

    return {
        "files": files_summary,
        "class4_passenger_car_taxonomy": {
            "total_item_group_nodes": len(class4_nodes),
            "top_level_groups_count": len(top_branches_c4),
            "max_tree_depth": max_depth,
            "class4_rfr_defect_items": len(class4_rfrs),
            "rfr_deficiency_categories": dict(def_cat_dist),
        },
        "rfr_locations_count": rfr_locations_count,
        "fuel_types": fuel_types,
        "test_outcomes": test_outcomes,
        "test_types": test_types,
        "mot_top_group_to_nhtsa_alignment": {
            "mapped_count": len(mapped_top),
            "total_top_groups": len(top_branches_c4),
            "coverage_pct": round(100.0 * len(mapped_top) / max(len(top_branches_c4), 1), 2),
            "mapped_top_groups": mapped_top,
            "unmapped_top_groups": unmapped_top,
        },
    }


def analyze_dtc_expansion() -> dict[str, Any]:
    codeslist_csv = RAW_DIR / "obd2-codes.csv"
    wal_db = EXT_DIR / "wal33d_dtc_codes.db"
    obdex_dir = EXT_DIR / "obdex"
    if not codeslist_csv.exists() or not wal_db.exists():
        return {"error": "Missing obd2-codes.csv or wal33d_dtc_codes.db; run with --fetch first."}

    # 1. Baseline CodesList
    cl_codes: set[str] = set()
    with codeslist_csv.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            c = (row.get("code") or "").strip().upper()
            if c:
                cl_codes.add(c)

    # 2. Wal33D SQLite (dtc_definitions)
    conn = sqlite3.connect(str(wal_db))
    cur = conn.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    table_schemas = {}
    for t in tables:
        cols = [r[1] for r in cur.execute(f"PRAGMA table_info('{t}')").fetchall()]
        cnt = cur.execute(f"SELECT COUNT(*) FROM '{t}'").fetchone()[0]
        table_schemas[t] = {"rows": cnt, "cols": cols}

    wal_all_codes: set[str] = set()
    wal_generic_codes: set[str] = set()
    wal_mfr_codes: set[str] = set()
    wal_mfr_dist: Counter[str] = Counter()
    wal_prefix_dist: Counter[str] = Counter()

    for code_raw, mfr_raw, typ_raw, is_gen in cur.execute(
        "SELECT code, manufacturer, type, is_generic FROM dtc_definitions"
    ):
        code = str(code_raw or "").strip().upper()
        if not code:
            continue
        wal_all_codes.add(code)
        wal_prefix_dist[str(typ_raw or code[:1]).upper()] += 1
        mfr_val = str(mfr_raw or "").strip().upper()
        if int(is_gen or 0) == 1 or mfr_val in {"", "GENERIC", "SAE"}:
            wal_generic_codes.add(code)
        else:
            wal_mfr_codes.add(code)
            wal_mfr_dist[mfr_val] += 1
    conn.close()

    # 3. OBDex YAML files (`- code: P0001` blocks)
    obdex_codes: set[str] = set()
    obdex_with_sources = 0
    obdex_with_de = 0
    for yf in sorted((obdex_dir / "data" / "generic").glob("*.yaml")):
        raw = yf.read_text(encoding="utf-8", errors="replace")
        blocks = re.split(r"(?=^- code:\s*)", raw, flags=re.M)
        for blk in blocks:
            m = re.match(r"^- code:\s*['\"]?([PCBU][0-9A-Za-z]{4})['\"]?", blk)
            if not m:
                continue
            obdex_codes.add(m.group(1).upper())
            if "\n  sources:" in blk:
                obdex_with_sources += 1
            if "\n    de:" in blk:
                obdex_with_de += 1

    pid_count = 0
    for pf in sorted((obdex_dir / "data" / "pids").glob("*.yaml")):
        raw = pf.read_text(encoding="utf-8", errors="replace")
        pid_count += len(re.findall(r"^- pid:\s*", raw, flags=re.M))

    # 4. NHTSA extracted Top 20 DTCs from join-stats.json
    top_nhtsa = []
    if JOIN_STATS_PATH.exists():
        js = json.loads(JOIN_STATS_PATH.read_text())
        top_nhtsa = js.get("joins_dtc_qa", {}).get("cmpl_narratives_dtc_regex", {}).get("top_dtc", [])

    top_nhtsa_eval = []
    baseline_hits = 0
    expanded_hits = 0
    newly_covered_mfr_codes = []
    # Check specific manufacturers in Wal33D for newly covered codes
    conn2 = sqlite3.connect(str(wal_db))
    wal_code_mfrs: dict[str, list[str]] = {}
    for c_item in top_nhtsa:
        c = c_item["code"].upper()
        rows_m = conn2.execute(
            "SELECT DISTINCT manufacturer FROM dtc_definitions WHERE UPPER(code)=?", (c,)
        ).fetchall()
        if rows_m:
            wal_code_mfrs[c] = sorted({str(r[0]) for r in rows_m if r[0]})
    conn2.close()

    for item in top_nhtsa:
        c = item["code"].upper()
        in_cl = c in cl_codes
        in_wal = c in wal_all_codes
        in_obdex = c in obdex_codes
        if in_cl:
            baseline_hits += 1
        if in_cl or in_wal or in_obdex:
            expanded_hits += 1
        if (not in_cl) and (in_wal or in_obdex):
            newly_covered_mfr_codes.append(c)
        top_nhtsa_eval.append({
            "code": c,
            "nhtsa_cmpl_rows": item.get("cmpl_rows_mention"),
            "in_codeslist": in_cl,
            "in_wal33d": in_wal,
            "wal33d_manufacturers": wal_code_mfrs.get(c, []),
            "in_obdex": in_obdex,
        })

    union_all = cl_codes | wal_all_codes | obdex_codes

    return {
        "codeslist_unique": len(cl_codes),
        "wal33d": {
            "tables": table_schemas,
            "unique_codes": len(wal_all_codes),
            "generic_codes": len(wal_generic_codes),
            "manufacturer_specific_codes": len(wal_mfr_codes),
            "distinct_manufacturers": len(wal_mfr_dist),
            "top_manufacturers": dict(wal_mfr_dist.most_common(15)),
            "honda_code_count": wal_mfr_dist.get("HONDA", 0),
            "prefix_distribution": dict(wal_prefix_dist),
            "new_unique_codes_over_codeslist": len(wal_all_codes - cl_codes),
        },
        "obdex": {
            "unique_codes_parsed": len(obdex_codes),
            "entries_with_sources_field": obdex_with_sources,
            "entries_with_de_translation": obdex_with_de,
            "pid_entries_parsed": pid_count,
            "new_unique_codes_over_codeslist": len(obdex_codes - cl_codes),
        },
        "combined_open_dtc_pool_unique": len(union_all),
        "net_gain_over_codeslist": len(union_all - cl_codes),
        "nhtsa_top20_extracted_eval": {
            "total": len(top_nhtsa_eval),
            "baseline_codeslist_hits": baseline_hits,
            "expanded_hits": expanded_hits,
            "newly_covered_non_generic_codes": newly_covered_mfr_codes,
            "details": top_nhtsa_eval,
        },
    }


def analyze_vss_vsso_and_opendbc() -> dict[str, Any]:
    vss_csv = EXT_DIR / "covesa_vss_v6.1.csv"
    vsso_core = EXT_DIR / "w3c_vsso" / "vsso-core.ttl"
    vsso_22 = EXT_DIR / "w3c_vsso" / "vss_rel_2.2.ttl"
    dbc_dir = EXT_DIR / "opendbc"

    out: dict[str, Any] = {}
    if vss_csv.exists():
        types: Counter[str] = Counter()
        l2_branches: Counter[str] = Counter()
        traction_battery_signals: list[str] = []
        electric_motor_signals: list[str] = []
        diagnostics_signals: list[str] = []
        adas_signals: list[str] = []
        total = 0
        with vss_csv.open("r", encoding="utf-8", errors="replace", newline="") as fh:
            reader = csv.DictReader(fh)
            cols = list(reader.fieldnames or [])
            for row in reader:
                total += 1
                sig = (row.get("Signal") or "").strip()
                tp = (row.get("Type") or "").strip()
                types[tp] += 1
                parts = sig.split(".")
                if len(parts) >= 2:
                    l2_branches[".".join(parts[:2])] += 1
                if tp != "branch":
                    if "TractionBattery" in sig or "Charging" in sig:
                        traction_battery_signals.append(sig)
                    elif "ElectricMotor" in sig:
                        electric_motor_signals.append(sig)
                    elif ".Diagnostics." in sig or ".OBD." in sig:
                        diagnostics_signals.append(sig)
                    elif ".ADAS." in sig:
                        adas_signals.append(sig)
        out["covesa_vss_v6_1"] = {
            "columns": cols,
            "total_nodes": total,
            "by_type": dict(types),
            "by_l2_domain": dict(l2_branches.most_common(20)),
            "traction_battery_and_charging_signals": len(traction_battery_signals),
            "traction_battery_examples": traction_battery_signals[:12],
            "electric_motor_signals": len(electric_motor_signals),
            "diagnostics_signals_count": len(diagnostics_signals),
            "diagnostics_signal_examples": diagnostics_signals[:10],
            "adas_signals_count": len(adas_signals),
            "adas_signal_examples": adas_signals[:12],
        }

    vsso_stats = {}
    for label, p in [("vsso_core_ttl", vsso_core), ("vss_rel_2_2_ttl", vsso_22)]:
        if p.exists():
            txt = p.read_text(encoding="utf-8", errors="replace")
            vsso_stats[label] = {
                "bytes": len(txt.encode("utf-8")),
                "owl_classes": len(re.findall(r"\b(?:owl:Class|rdfs:Class|vsso-core:Branch|vsso-core:ObservableSignal|vsso-core:ActuatableSignal)\b", txt)),
                "sosa_links": len(re.findall(r"\bsosa:", txt)),
                "object_properties": len(re.findall(r"\bowl:ObjectProperty\b", txt)),
                "datatype_properties": len(re.findall(r"\bowl:DatatypeProperty\b", txt)),
            }
    out["w3c_vsso"] = vsso_stats

    dbc_stats = {}
    if dbc_dir.exists():
        for dp in sorted(dbc_dir.glob("*.dbc")):
            txt = dp.read_text(encoding="utf-8", errors="replace")
            bo_msgs = re.findall(r"^BO_\s+\d+\s+([A-Za-z0-9_]+)\s*:", txt, re.M)
            sg_sigs = re.findall(r"^\s+SG_\s+([A-Za-z0-9_]+)\s*:", txt, re.M)
            domain_hits: Counter[str] = Counter()
            for s in sg_sigs + bo_msgs:
                up = s.upper()
                if any(k in up for k in ("BRAKE", "AEB", "CMBS", "ABS")):
                    domain_hits["SERVICE_BRAKES_OR_AEB"] += 1
                if any(k in up for k in ("STEER", "EPS", "LKAS", "TORQUE")):
                    domain_hits["STEERING_OR_ADAS"] += 1
                if any(k in up for k in ("BATT", "BMS", "SOC", "CELL", "VOLT", "CHARG", "HV")):
                    domain_hits["EV_BATTERY_CHARGING"] += 1
                if any(k in up for k in ("ENG", "RPM", "THROTTLE", "FUEL", "COOLANT")):
                    domain_hits["ENGINE_POWERTRAIN"] += 1
            dbc_stats[dp.name] = {
                "messages_BO": len(bo_msgs),
                "signals_SG": len(sg_sigs),
                "domain_signal_hits": dict(domain_hits),
                "sample_messages": bo_msgs[:8],
            }
    out["commaai_opendbc"] = dbc_stats
    return out


def build_track2_summary(academic_meta: dict[str, Any] | None) -> dict[str, Any]:
    if not academic_meta and (EXT_DIR / "academic_metadata.json").exists():
        academic_meta = json.loads((EXT_DIR / "academic_metadata.json").read_text())
    return {
        "academic_ev_bms_and_fault_datasets": academic_meta or {},
        "new_ontology_capability_slots_evidenced": [
            {
                "domain": "EV Traction Battery & BMS Faults (Track 2)",
                "evidence_sources": [
                    "Figshare 23659323 / 30162841",
                    "Figshare 23301881 (EVBattery)",
                    "Zenodo 10656500 / 19006180 / 18328700",
                    "COVESA VSS TractionBattery.*",
                    "opendbc byd_atto3 / tesla_powertrain",
                ],
                "candidate_slots": [
                    "cellVoltageEnvelope",
                    "cellTemperature",
                    "stateOfCharge",
                    "stateOfHealth",
                    "insulationResistance",
                    "chargingSessionPhase",
                    "thermalRunawayFlag",
                    "microShortCircuitFlag",
                ],
            },
            {
                "domain": "Periodic Inspection & Mileage Defect History (Track 1)",
                "evidence_sources": ["UK DVSA MOT Testing Data (lookup.zip + annual test_result/test_item)"],
                "candidate_slots": [
                    "testMileage",
                    "firstUseYear",
                    "fuelTypeCode",
                    "motTestOutcome",
                    "rfrItemGroup",
                    "rfrLocation",
                    "defectSeverity",
                ],
            },
            {
                "domain": "Cross-Border Recall Alignment (Track 1)",
                "evidence_sources": ["Transport Canada VRDB (vrdb_full_monthly.csv)", "NHTSA FLAT_RCL"],
                "candidate_slots": [
                    "manufacturerRecallNumber",
                    "jurisdictionRecallId",
                    "recallCategory",
                    "unitsAffected",
                ],
            },
            {
                "domain": "Structured Symptom -> Diagnostic Flowchart -> Resolution (Track 1/2)",
                "evidence_sources": ["Zenodo 15626055 (Automotive Faults Dataset)"],
                "candidate_slots": ["symptomList", "diagnosticProcedureSteps", "resolutionOutcome"],
            },
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="下载并双轨探查跨平台扩展公开数据源")
    parser.add_argument("--fetch", action="store_true", help="下载免登录直链 A 级样本与元数据到 data/raw/")
    args = parser.parse_args(argv)

    fetched: dict[str, Any] = {}
    if args.fetch:
        EXT_DIR.mkdir(parents=True, exist_ok=True)
        fetched = fetch_all()
    elif (EXT_DIR / "fetch_manifest.json").exists():
        fetched["endpoints"] = json.loads((EXT_DIR / "fetch_manifest.json").read_text())

    tc_nhtsa = analyze_transport_canada_vs_nhtsa()
    uk_mot = analyze_uk_mot_lookup()
    dtc_exp = analyze_dtc_expansion()
    vss_dbc = analyze_vss_vsso_and_opendbc()
    track2 = build_track2_summary(fetched.get("academic"))

    tz_sh = timezone(timedelta(hours=8))
    now_str = datetime.now(tz_sh).strftime("%Y-%m-%d %H:%M Asia/Shanghai")

    report = {
        "measured_at": now_str,
        "privacy_note": "Metadata, field names, taxonomy counts, and join rates only. Zero VINs, zero PII, zero raw narratives.",
        "verified_endpoints": fetched.get("endpoints", []),
        "track1_global_and_diagnostic_joins": {
            "transport_canada_recalls_vs_nhtsa": tc_nhtsa,
            "uk_dvsa_mot_taxonomy": uk_mot,
            "open_dtc_expansion_vs_baseline": dtc_exp,
            "covesa_vss_vsso_and_opendbc": vss_dbc,
        },
        "track2_nev_and_chinese_profiling": track2,
    }

    OUT_STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_STATS_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"WROTE {OUT_STATS_PATH} ({OUT_STATS_PATH.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
