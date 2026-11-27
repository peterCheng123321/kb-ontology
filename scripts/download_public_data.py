#!/usr/bin/env python3
"""下载本试验用到的公开数据到 data/raw/（该目录不进 git）。

默认只下载字段字典等小文件，并打印全部直接链接。
大型平面文件请加 --fetch-large。下载后请勿把车辆识别号或投诉叙述写入本仓库。

来源与许可证见仓库根目录 README.md、NOTICE 与 docs/PUBLIC-DATASETS-HF.md。
"""
from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW = REPO_ROOT / "data" / "raw"

# 2026-11-24 / 2026-11-25 核对可访问的直接链接（返回 HTTP 200）。
NHTSA_PORTAL = "https://www.nhtsa.gov/nhtsa-datasets-and-apis"
EXTENDED_DIR = RAW / "extended"

SMALL_FILES = {
    "CMPL.txt": "https://static.nhtsa.gov/odi/ffdd/cmpl/CMPL.txt",
    "RCL.txt": "https://static.nhtsa.gov/odi/ffdd/rcl/RCL.txt",
    "INV.txt": "https://static.nhtsa.gov/odi/ffdd/inv/INV.txt",
    "TSBS.txt": "https://static.nhtsa.gov/odi/ffdd/tsbs/TSBS.txt",
}

LARGE_FILES = {
    "FLAT_CMPL.zip": "https://static.nhtsa.gov/odi/ffdd/cmpl/FLAT_CMPL.zip",
    "FLAT_RCL_POST_2010.zip": "https://static.nhtsa.gov/odi/ffdd/rcl/FLAT_RCL_POST_2010.zip",
    "FLAT_RCL_PRE_2010.zip": "https://static.nhtsa.gov/odi/ffdd/rcl/FLAT_RCL_PRE_2010.zip",
    "FLAT_INV.zip": "https://static.nhtsa.gov/odi/ffdd/inv/FLAT_INV.zip",
    "TSBS_RECEIVED_2015-2019.zip": "https://static.nhtsa.gov/odi/ffdd/tsbs/TSBS_RECEIVED_2015-2019.zip",
    "TSBS_RECEIVED_2020-2024.zip": "https://static.nhtsa.gov/odi/ffdd/tsbs/TSBS_RECEIVED_2020-2024.zip",
    "TSBS_RECEIVED_2025-2026.zip": "https://static.nhtsa.gov/odi/ffdd/tsbs/TSBS_RECEIVED_2025-2026.zip",
    "MFR_COMMS_RECEIVED_2015-2019.zip": "https://static.nhtsa.gov/odi/ffdd/tsbs/MFR_COMMS_RECEIVED_2015-2019.zip",
    "MFR_COMMS_RECEIVED_2020-2024.zip": "https://static.nhtsa.gov/odi/ffdd/tsbs/MFR_COMMS_RECEIVED_2020-2024.zip",
    "MFR_COMMS_RECEIVED_2025-2026.zip": "https://static.nhtsa.gov/odi/ffdd/tsbs/MFR_COMMS_RECEIVED_2025-2026.zip",
}

HF_DATASETS = [
    ("wushan/vehicle_qa", "https://huggingface.co/datasets/wushan/vehicle_qa", "Apache-2.0", "中文故障问诊"),
    ("CodesList/obd2-codes", "https://huggingface.co/datasets/CodesList/obd2-codes", "CC BY 4.0（需署名）", "DTC 词表"),
    ("Ichlibitiche/mechanicdb-obd2-repair-sample", "https://huggingface.co/datasets/Ichlibitiche/mechanicdb-obd2-repair-sample", "ODbL 1.0", "故障码到维修步骤与零件的样本"),
    ("BAAI/IndustryInstruction_Automobiles", "https://huggingface.co/datasets/BAAI/IndustryInstruction_Automobiles", "Apache-2.0", "中英汽车指令问答"),
    ("BAAI/IndustryCorpus_automobile", "https://huggingface.co/datasets/BAAI/IndustryCorpus_automobile", "Apache-2.0", "汽车领域网页语料"),
    ("BAAI/IndustryCorpus2_automobile", "https://huggingface.co/datasets/BAAI/IndustryCorpus2_automobile", "Apache-2.0", "汽车领域网页语料（后续版本）"),
    ("PedroCuisinier2025/OBD2_panel_opel_2012", "https://huggingface.co/datasets/PedroCuisinier2025/OBD2_panel_opel_2012", "以数据集卡片为准", "OBD-II PID / 遥测字段形状"),
]

# 第二阶段新增 A 级免登录直链扩展源（小文件字典、开源码表与车辆信号标准）
EXTENDED_SMALL_FILES = {
    "uk_mot_lookup.zip": "https://data.dft.gov.uk/anonymised-mot-test/lookup.zip",
    "wal33d_dtc_codes.db": "https://raw.githubusercontent.com/Wal33D/dtc-database/main/data/dtc_codes.db",
    "covesa_vss_v6.1.csv": "https://github.com/COVESA/vehicle_signal_specification/releases/download/v6.1/vss.csv",
    "w3c_vsso/vsso-core.ttl": "https://raw.githubusercontent.com/w3c/vsso/gh-pages/spec/vsso-core.ttl",
    "w3c_vsso/vss_rel_2.2.ttl": "https://raw.githubusercontent.com/w3c/vsso/gh-pages/spec/vss_rel_2.2.ttl",
}

EXTENDED_LARGE_FILES = {
    "vrdb_full_monthly.csv": "https://opendatatc.tc.canada.ca/vrdb_full_monthly.csv",
}

# 第一阶段基线切片重建所需文件（--include-baseline）
BASELINE_FILES = {
    "COMPLAINTS_RECEIVED_2020-2024.zip": "https://static.nhtsa.gov/odi/ffdd/cmpl/COMPLAINTS_RECEIVED_2020-2024.zip",
    "COMPLAINTS_RECEIVED_2025-2026.zip": "https://static.nhtsa.gov/odi/ffdd/cmpl/COMPLAINTS_RECEIVED_2025-2026.zip",
    "FLAT_RCL_POST_2010.zip": "https://static.nhtsa.gov/odi/ffdd/rcl/FLAT_RCL_POST_2010.zip",
    "FLAT_INV.zip": "https://static.nhtsa.gov/odi/ffdd/inv/FLAT_INV.zip",
    "TSBS_RECEIVED_2015-2019.zip": "https://static.nhtsa.gov/odi/ffdd/tsbs/TSBS_RECEIVED_2015-2019.zip",
    "TSBS_RECEIVED_2020-2024.zip": "https://static.nhtsa.gov/odi/ffdd/tsbs/TSBS_RECEIVED_2020-2024.zip",
    "TSBS_RECEIVED_2025-2026.zip": "https://static.nhtsa.gov/odi/ffdd/tsbs/TSBS_RECEIVED_2025-2026.zip",
    "obd2-codes.csv": "https://huggingface.co/datasets/CodesList/obd2-codes/resolve/main/obd2-codes.csv",
    "hf/vehicle_qa/train.csv": "https://huggingface.co/datasets/wushan/vehicle_qa/resolve/main/train.csv",
    "hf/vehicle_qa/test.csv": "https://huggingface.co/datasets/wushan/vehicle_qa/resolve/main/test.csv",
    "hf/mechanicdb/dtc_codes.parquet": "https://huggingface.co/datasets/Ichlibitiche/mechanicdb-obd2-repair-sample/resolve/main/dtc_codes.parquet",
    "hf/mechanicdb/diagnostic_fixes.parquet": "https://huggingface.co/datasets/Ichlibitiche/mechanicdb-obd2-repair-sample/resolve/main/diagnostic_fixes.parquet",
    "hf/mechanicdb/dtc_fixes_joined.parquet": "https://huggingface.co/datasets/Ichlibitiche/mechanicdb-obd2-repair-sample/resolve/main/dtc_fixes_joined.parquet",
    "hf/mechanicdb/replacement_parts.parquet": "https://huggingface.co/datasets/Ichlibitiche/mechanicdb-obd2-repair-sample/resolve/main/replacement_parts.parquet",
}

# 第三阶段 v3 本体实验扩展大包（--include-v3-extras）
V3_EXTRA_FILES = {
    "uk_mot_2023/dft_test_result_2023.zip": "https://data.dft.gov.uk/anonymised-mot-test/test_data/dft_test_result_2023.zip",
    "uk_mot_2023/dft_test_item_2023.zip": "https://data.dft.gov.uk/anonymised-mot-test/test_data/dft_test_item_2023.zip",
    "figshare_30162841/battery_dataset.zip": "https://ndownloader.figshare.com/files/58088389",
}

EXTENDED_CATALOG = [
    ("Transport Canada VRDB", "https://opendatatc.tc.canada.ca/vrdb_full_monthly.csv", "Open Government Licence - Canada", "加拿大全量召回（含厂内召回号与系统分类）"),
    ("UK DVSA MOT Lookup & Results", "https://data.dft.gov.uk/anonymised-mot-test/lookup.zip", "UK Open Government Licence (OGL)", "英国实车定期年检缺陷树、严重度、三维位置与新能源燃料枚举"),
    ("Wal33D/dtc-database", "https://github.com/Wal33D/dtc-database", "MIT", "12,128 唯一码（含 33 个主机厂厂标定义）"),
    ("foerbsnavi/OBDex", "https://github.com/foerbsnavi/OBDex", "CC0-1.0（数据）/ MIT（代码）", "9,533 条带外部溯源的通用 SAE J2012 码表及 132 个 Mode 01/09 PID"),
    ("COVESA VSS v6.1", "https://github.com/COVESA/vehicle_signal_specification", "MPL-2.0", "1,737 个标准车辆信号节点（含动力电池、电驱、ADAS）"),
    ("W3C VSSo", "https://github.com/w3c/vsso", "CC-BY-4.0（本体）/ Apache-2.0（代码）", "基于 SOSA/SSN 的车辆信号语义网对齐模板"),
    ("commaai/opendbc", "https://github.com/commaai/opendbc", "MIT", "Honda / BYD / Tesla 实车 CAN DBC 报文与信号定义"),
    ("Figshare EVBattery & Battery Faults", "https://figshare.com/articles/dataset/EVBattery_A_Large-Scale_Electric_Vehicle_Dataset_for_Battery_Health_and_Capacity_Estimation/23301881", "CC-BY-4.0", "实车新能源动力电池充电时序、健康/容量与异常标注"),
    ("Zenodo BMS Faults & Automotive Faults", "https://zenodo.org/doi/10.5281/zenodo.15626055", "CC-BY-4.0", "515 车 BMS 云端高危故障及故障—症状—诊断流程图 JSON（浏览器下载）"),
]


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"下载 {url}")
    print(f"  -> {dest}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; kb-ontology-poc/3.0)"})
    with urllib.request.urlopen(req, timeout=300) as resp, tmp.open("wb") as out:
        while True:
            chunk = resp.read(1024 * 512)
            if not chunk:
                break
            out.write(chunk)
    tmp.replace(dest)
    print(f"  完成 {dest.stat().st_size} 字节")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="下载公开数据到 data/raw/，或只打印直接链接。")
    parser.add_argument("--fetch-large", action="store_true", help="同时下载 NHTSA 大型平面文件（数百 MB 量级）")
    parser.add_argument("--include-extended", action="store_true", help="同时打印或下载第二阶段扩展 A 级源（政府/GitHub/学术开放源）")
    parser.add_argument("--include-baseline", action="store_true", help="下载第一阶段基线切片重建所需 NHTSA/HF 文件")
    parser.add_argument("--include-v3-extras", action="store_true", help="下载第三阶段 v3 实验所需 MOT 2023 年度包与 Figshare 30162841")
    parser.add_argument("--dry-run", action="store_true", help="只打印链接，不下载")
    args = parser.parse_args(argv)

    print("NHTSA 官方说明页：", NHTSA_PORTAL)
    print()
    print("字段字典：")
    for name, url in SMALL_FILES.items():
        print(f"  {name}: {url}")
    print()
    print("大型平面文件：")
    for name, url in LARGE_FILES.items():
        print(f"  {name}: {url}")
    print()
    print("Hugging Face 数据集（请按各页说明下载，注意许可证）：")
    for name, url, lic, purpose in HF_DATASETS:
        print(f"  {name}")
        print(f"    {url}")
        print(f"    许可证：{lic}；用途：{purpose}")

    if args.include_extended:
        print()
        print("第二阶段扩展 A 级公开源（详见 docs/PUBLIC-DATASETS-EXTENDED.md）：")
        for name, url in EXTENDED_SMALL_FILES.items():
            print(f"  [小文件/字典] {name}: {url}")
        for name, url in EXTENDED_LARGE_FILES.items():
            print(f"  [大型平面表] {name}: {url}")
        for name, url, lic, purpose in EXTENDED_CATALOG:
            print(f"  {name}")
            print(f"    {url}")
            print(f"    许可证：{lic}；用途：{purpose}")

    if args.include_baseline:
        print()
        print("第一阶段基线切片重建源（--include-baseline）：")
        for name, url in BASELINE_FILES.items():
            print(f"  {name}: {url}")

    if args.include_v3_extras:
        print()
        print("第三阶段 v3 扩展实测大包（--include-v3-extras）：")
        for name, url in V3_EXTRA_FILES.items():
            print(f"  {name}: {url}")

    if args.dry_run:
        return 0

    RAW.mkdir(parents=True, exist_ok=True)
    for name, url in SMALL_FILES.items():
        dest = RAW / name
        if dest.exists() and dest.stat().st_size > 0:
            print(f"已存在，跳过 {dest}")
            continue
        download(url, dest)

    if args.fetch_large:
        for name, url in LARGE_FILES.items():
            dest = RAW / name
            if dest.exists() and dest.stat().st_size > 0:
                print(f"已存在，跳过 {dest}")
                continue
            download(url, dest)
    elif not args.include_baseline and not args.include_v3_extras:
        print("\n未加 --fetch-large，跳过大型平面文件。需要时请重新运行并加上该参数。")

    if args.include_baseline:
        for name, url in BASELINE_FILES.items():
            dest = RAW / name
            if dest.exists() and dest.stat().st_size > 0:
                print(f"已存在，跳过 {dest}")
                continue
            download(url, dest)

    if args.include_extended:
        EXTENDED_DIR.mkdir(parents=True, exist_ok=True)
        for name, url in EXTENDED_SMALL_FILES.items():
            dest = EXTENDED_DIR / name
            if dest.exists() and dest.stat().st_size > 0:
                print(f"已存在，跳过 {dest}")
                continue
            download(url, dest)
        if args.fetch_large:
            for name, url in EXTENDED_LARGE_FILES.items():
                dest = EXTENDED_DIR / name
                if dest.exists() and dest.stat().st_size > 0:
                    print(f"已存在，跳过 {dest}")
                    continue
                download(url, dest)
        else:
            print("\n未加 --fetch-large，跳过扩展大型平面表（如加拿大 VRDB 186 MB）。完整双轨探查请运行 python3 scripts/probe_extended_datasets.py --fetch。")

    if args.include_v3_extras:
        EXTENDED_DIR.mkdir(parents=True, exist_ok=True)
        for name, url in V3_EXTRA_FILES.items():
            dest = EXTENDED_DIR / name
            if dest.exists() and dest.stat().st_size > 0:
                print(f"已存在，跳过 {dest}")
                continue
            download(url, dest)

    print("\nHugging Face、Kaggle 与 Zenodo 数据集请按各页说明与许可证获取，不要把原始文件提交到 git。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
