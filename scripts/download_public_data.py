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

# 2026-11-24 核对可访问的直接链接（static.nhtsa.gov 与 Hugging Face 返回 HTTP 200）。
NHTSA_PORTAL = "https://www.nhtsa.gov/nhtsa-datasets-and-apis"

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


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"下载 {url}")
    print(f"  -> {dest}")
    with urllib.request.urlopen(url, timeout=120) as resp, dest.open("wb") as out:
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            out.write(chunk)
    print(f"  完成 {dest.stat().st_size} 字节")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="下载公开数据到 data/raw/，或只打印直接链接。")
    parser.add_argument("--fetch-large", action="store_true", help="同时下载 NHTSA 大型平面文件（数百 MB 量级）")
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
    else:
        print("\n未加 --fetch-large，跳过大型平面文件。需要时请重新运行并加上该参数。")

    print("\nHugging Face 数据集请用 datasets 库或浏览器从上面的链接获取，不要把原始文件提交到 git。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
