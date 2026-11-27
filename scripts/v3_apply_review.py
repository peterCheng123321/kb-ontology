#!/usr/bin/env python3
"""Record structured-field human review samples (up to 10 per new v3 CandidateLink family)
and write both review/v3_review_samples.json (gitignored detailed working file) and
docs/stats/v3-review.json (committed summary & sample table for user spot-check).

Protocol:
  - Judgments rely strictly on official recall text, standardized taxonomy/DBC/VSS labels,
    OBDex PID definitions, and structured metadata — NEVER raw consumer narratives.
  - 'accepted' means plausible at structured-field level, NOT legal/OEM root-cause confirmation.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REV_DIR = REPO_ROOT / "review"
STATS_DIR = REPO_ROOT / "docs" / "stats"
POOL_PATH = REV_DIR / "v3_candidate_pool.json"

# Structured-field human review judgments keyed by exact link_id
JUDGMENTS: dict[str, tuple[str, str]] = {
    # 1. xjur_mmy_system_window (all 7 generated cross-border Honda 2018 recall pairs)
    "xjur-18V629000-CA_2018500": (
        "accepted",
        "发布日期差 0 天，美加官方摘要均明确为 2018 雅阁倒车影像中控不显示软件故障（FMVSS/CMVSS 111），同源跨国召回成立。",
    ),
    "xjur-20V314000-CA_2020236": (
        "accepted",
        "发布日期差 0 天，美加官方摘要均明确为 2018 雅阁低压燃油泵失效导致熄火，同源跨国召回成立。",
    ),
    "xjur-20V771000-CA_2020611": (
        "accepted",
        "发布日期差 0 天，美加官方摘要均明确为 2018 雅阁车身控制模块（BCM）软件通信中断，同源跨国召回成立。",
    ),
    "xjur-23V158000-CA_2023127": (
        "accepted",
        "发布日期差 0 天，美加官方摘要均明确为 2018 CR-V/雅阁前排安全带锁扣缺陷，同源跨国召回成立。",
    ),
    "xjur-23V858000-CA_2023679": (
        "accepted",
        "发布日期差 0 天，美加均指向 2018 CR-V/雅阁低压燃油泵召回；加方官方摘要注明后续由 2024-262 替代。",
    ),
    "xjur-23V858000-CA_2024262": (
        "accepted",
        "日期差 140 天，加方官方摘要显式说明 2024-262 替代 2023-679 且同为低压燃油泵召回，属于跨国替代活动有效对应。",
    ),
    "xjur-26V332000-CA_2026251": (
        "accepted",
        "发布日期差 0 天，美加均明确为 2018 CR-V/雅阁前排乘客座椅重量传感器缺陷影响气囊展开，同源跨国召回成立。",
    ),
    # 2. dtc_make_context (10 samples: 6 cross-brand mismatches rejected, 4 SAE generic accepted)
    "dmc-P1326-VOLKSWAGEN-wal33d": (
        "rejected",
        "跨品牌冲突：Wal33D 仅收录 VOLKSWAGEN 释义，而 NHTSA 高频投诉属现代/起亚 KSDS，更不可套用到本田上下文（mismatchFlag=true）。",
    ),
    "dmc-P0300-AUDI-wal33d": (
        "rejected",
        "跨品牌冗余：AUDI 厂标条目包含排查建议文本而非标准定义，套用于本田上下文应拒绝并优先采用 SAE GENERIC。",
    ),
    "dmc-P0301-AUDI-wal33d": (
        "rejected",
        "跨品牌冗余：AUDI 厂标释义不应套用于本田 2018 投诉，应使用 SAE J2012 通用定义。",
    ),
    "dmc-B1234-OTHER-wal33d": (
        "rejected",
        "Wal33D 归类为未定厂商 OTHER（Mirror Switch），无本田官方厂标佐证，禁止直接套用。",
    ),
    "dmc-C1250-OTHER-wal33d": (
        "rejected",
        "Wal33D 归类为未定厂商 OTHER 的底盘厂标码，无法确认与本田 2018 底盘码义一致。",
    ),
    "dmc-C1870-OTHER-wal33d": (
        "rejected",
        "Wal33D 归类为 OTHER（Air Suspension Gate Solenoid），本田 CR-V/雅阁 2018 无空气悬架配置，明显跨厂误配。",
    ),
    "dmc-P0300-GENERIC-obdex": (
        "accepted",
        "SAE J2012 标准通用随机/多缸失火码，OBDex 经外部溯源审校且英德释义清晰，可安全用于本田。",
    ),
    "dmc-P0172-GENERIC-obdex": (
        "accepted",
        "SAE J2012 标准通用燃油系统过浓码，OBDex 定义准确且与燃油系统切片高度相关。",
    ),
    "dmc-B0020-GENERIC-codeslist": (
        "accepted",
        "SAE J2012 通用车身侧气囊展开控制码，CodesList/Wal33D/OBDex 三库释义完全一致。",
    ),
    "dmc-P0420-GENERIC-wal33d": (
        "accepted",
        "SAE J2012 通用三元催化效率低于阈值码，跨库通用定义一致。",
    ),
    # 3. component_mot_group (10 samples: 7 accepted, 3 uncertain due to scope breadth)
    "cmot-SERVICE_BRAKES-20003": (
        "accepted",
        "SKOS exactMatch：MOT Class 4 Brakes（20003）与 NHTSA SERVICE BRAKES 语义等价。",
    ),
    "cmot-STEERING-20106": (
        "accepted",
        "SKOS exactMatch：MOT Class 4 Steering（20106）与 NHTSA STEERING 语义等价。",
    ),
    "cmot-VISIBILITY-20147": (
        "accepted",
        "SKOS exactMatch：MOT Class 4 Visibility（20147）与 NHTSA VISIBILITY 语义等价。",
    ),
    "cmot-SUSPENSION-20218": (
        "accepted",
        "SKOS exactMatch：MOT Class 4 Suspension（20218）与 NHTSA SUSPENSION 语义等价。",
    ),
    "cmot-WHEELS-20448": (
        "accepted",
        "SKOS exactMatch：MOT Class 4 Road Wheels（20448）与 NHTSA WHEELS 语义等价。",
    ),
    "cmot-SEAT_BELTS-20431": (
        "accepted",
        "SKOS exactMatch：MOT Seat belt installation check（20431）精准对应 SEAT BELTS。",
    ),
    "cmot-EXTERIOR_LIGHTING-20158": (
        "accepted",
        "SKOS closeMatch：MOT 20158 含灯光、反光镜与电气设备，对外部灯光统计方向准确，需注明略宽。",
    ),
    "cmot-ELECTRICAL_SYSTEM-20158": (
        "uncertain",
        "MOT 20158 偏重外部灯光/蓄电池与基础线路，范围窄于 NHTSA 广义 ELECTRICAL SYSTEM（含 BCM/车机/传感器）。",
    ),
    "cmot-FUEL_SYSTEM-20385": (
        "uncertain",
        "MOT 20385（Noise, emissions and leaks）包含燃油渗漏但也混杂排气噪声，归属燃油系统时范围过宽。",
    ),
    "cmot-ENGINE-20385": (
        "uncertain",
        "MOT 20385 仅检验排放与渗漏，不能代表 NHTSA 发动机机械/失火投诉全集，仅作弱对应。",
    ),
    # 4. component_can_message (10 samples: 8 accepted, 2 uncertain indirect mapping)
    "ccan-FORWARD_COLLISION_AVOIDANCE-_bosch_radar_acc-ACC_CONTROL": (
        "accepted",
        "本田 2018 Bosch 雷达 ACC/FCW 减速度控制报文，精准对应前向碰撞避免。",
    ),
    "ccan-FORWARD_COLLISION_AVOIDANCE-_bosch_2018-RADAR_HUD": (
        "accepted",
        "本田 Bosch 雷达 CMBS/FCW 预警显示报文，直接关联前向碰撞避免。",
    ),
    "ccan-STEERING-_bosch_2018-STEERING_CONTROL": (
        "accepted",
        "本田 Bosch LKAS/EPS 转向力矩控制报文，精准对应转向系统。",
    ),
    "ccan-STEERING-_bosch_2018-STEER_STATUS": (
        "accepted",
        "本田 EPS 转向力矩与故障标志报文，精准对应转向系统。",
    ),
    "ccan-SERVICE_BRAKES-_bosch_2018-BRAKE_MODULE": (
        "accepted",
        "本田 Bosch 液压制动模块压力与踏板状态报文，精准对应制动系统。",
    ),
    "ccan-SERVICE_BRAKES-_honda_common-VSA_STATUS": (
        "accepted",
        "本田 VSA 车辆稳定辅助制动干预报文，合理关联行车制动。",
    ),
    "ccan-SEAT_BELTS-_honda_common-SEATBELT_STATUS": (
        "accepted",
        "本田主副驾安全带锁扣状态报文，与安全带主类及 23V158000 召回直接对应。",
    ),
    "ccan-LANE_DEPARTURE-_bosch_2018-LKAS_HUD_A": (
        "accepted",
        "本田 LKAS 车道保持仪表提示报文，精准对应车道偏离系统。",
    ),
    "ccan-FUEL_SYSTEM-_honda_common-ENGINE_DATA": (
        "uncertain",
        "ENGINE_DATA 仅暴露转速与车速，不直接含低压油泵压力信号，与燃油系统属间接关联。",
    ),
    "ccan-BACK_OVER_PREVENTION-honda_crv_ex_2017_body-BSM_STATUS_RIGHT": (
        "uncertain",
        "盲区监测雷达涉及侧后方来车预警，但与 18V629000 倒车摄像头中控显示并非同一传感器。",
    ),
    # 5. dtc_pid_subsystem (10 samples: 7 accepted powertrain PIDs, 3 uncertain body/chassis indirect)
    "dpid-P0300-01-0C": (
        "accepted",
        "多缸失火（P0300）核心需监测发动机转速（PID 01-0C）波动，J2012 P03xx 映射合理。",
    ),
    "dpid-P0300-01-0E": (
        "accepted",
        "多缸失火（P0300）直接关联点火提前角（PID 01-0E），映射合理。",
    ),
    "dpid-P0300-01-06": (
        "accepted",
        "失火排查需同步观察短期燃油修正（PID 01-06）以区分空燃比与点火因素，映射合理。",
    ),
    "dpid-P0300-01-23": (
        "accepted",
        "燃油压力不足可引发多缸失火，油轨压力（PID 01-23）具直接诊断价值。",
    ),
    "dpid-P0172-01-06": (
        "accepted",
        "系统过浓（P0172）首要验证项即 Bank 1 短期燃油修正（PID 01-06），映射精准。",
    ),
    "dpid-P0172-01-07": (
        "accepted",
        "系统过浓（P0172）触发判据直接依赖长期燃油修正（PID 01-07），映射精准。",
    ),
    "dpid-P0172-01-10": (
        "accepted",
        "空气流量计（MAF，PID 01-10）漂移是 P0172 典型诱因，映射合理。",
    ),
    "dpid-P0172-01-14": (
        "accepted",
        "上游氧传感器电压/修正（PID 01-14）为 P0172 闭环核心信号，映射合理。",
    ),
    "dpid-B0020-01-01": (
        "uncertain",
        "Mode 01 仅暴露排放就绪与 MIL 状态，不读取 SRS 安全气囊点火回路阻值（需 UDS 扩展服务），仅属弱提示。",
    ),
    "dpid-C0023-01-0D": (
        "uncertain",
        "车速 PID（01-0D）与底盘制动灯开关（C0023）仅间接相关，底盘诊断需依赖厂商 UDS DID。",
    ),
    # 6. battery_fault_signal (10 samples across all 3 EV brands: 8 accepted, 2 uncertain SOH proxy)
    "ebfs-battery_brand1-car105-Current": (
        "accepted",
        "brand1 异常充电片段沿动力电池 SOC（StateOfCharge.Current）演化，VSS 路径语义一致。",
    ),
    "ebfs-battery_brand1-car105-Min": (
        "accepted",
        "单体最低电压（CellVoltage.Min）是实车锂电故障诊断核心判据，与数据集任务定义一致。",
    ),
    "ebfs-battery_brand1-car105-Max": (
        "accepted",
        "最高电芯温度（Temperature.Max）对应充电热异常监测，但须注明纯 CSV 版不含原始温度波形。",
    ),
    "ebfs-battery_brand1-car105-StateOfHealth": (
        "uncertain",
        "纯 CSV 仅提供累计里程与充电片段数作 SOH 间接代理，缺乏实测容量标定值，属弱关联。",
    ),
    "ebfs-battery_brand2-car204-Current": (
        "accepted",
        "brand2 高频异常车（19,423 故障片段）对应 SOC 充电轨迹信号，VSS 对齐合理。",
    ),
    "ebfs-battery_brand2-car204-Min": (
        "accepted",
        "brand2 异常充电诊断直接关注单体最低电压异常压降，VSS 路径准确。",
    ),
    "ebfs-battery_brand2-car204-Max": (
        "accepted",
        "brand2 异常充电监测包含最高温度维度，语义一致（原始波形留待安全格式验证）。",
    ),
    "ebfs-battery_brand3-car404-Current": (
        "accepted",
        "brand3 高里程异常车（均值 20,409 km）充电片段对齐 VSS TractionBattery SOC 合理。",
    ),
    "ebfs-battery_brand3-car404-Min": (
        "accepted",
        "brand3 故障车辆对齐单体最低电压信号语义准确。",
    ),
    "ebfs-battery_brand3-car404-StateOfHealth": (
        "uncertain",
        "高里程（2 万 km+）虽与电池老化相关，但未见实测容量 SOH 数值，仅作弱关联。",
    ),
}


def main() -> int:
    pool = json.loads(POOL_PATH.read_text(encoding="utf-8"))
    pool_by_id: dict[str, tuple[str, dict]] = {}
    for method, items in pool.items():
        for it in items:
            pool_by_id[it["link_id"]] = (method, it)

    reviewed_items = []
    by_method_counts: dict[str, Counter] = defaultdict(Counter)
    missing = []
    for lid, (judgment, reason) in JUDGMENTS.items():
        if lid not in pool_by_id:
            missing.append(lid)
            continue
        method, meta = pool_by_id[lid]
        by_method_counts[method][judgment] += 1
        rec = {
            "link_id": lid,
            "method": method,
            "judgment": judgment,
            "reason": reason,
            "basis": "Structured/official fields only (no raw consumer complaint narratives or QA dialogues).",
            "evidence": {k: v for k, v in meta.items() if k != "link_id"},
        }
        reviewed_items.append(rec)

    if missing:
        print(f"WARNING: {len(missing)} judgment IDs not found in pool: {missing}", file=sys.stderr)

    overall = Counter(r["judgment"] for r in reviewed_items)
    full_payload = {
        "measured_at": "2026-11-25 Asia/Shanghai",
        "protocol": "Up to 10 sampled edges per new v3 CandidateLink family reviewed strictly from official/structured fields.",
        "total_reviewed": len(reviewed_items),
        "overall_counts": dict(overall),
        "by_method_counts": {m: dict(c) for m, c in sorted(by_method_counts.items())},
        "items": reviewed_items,
    }

    (REV_DIR / "v3_review_samples.json").write_text(
        json.dumps(full_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # Also write concise committed review summary (with truncated evidence <= 220 chars, zero PII)
    committed_items = []
    for r in reviewed_items:
        ev_short = {}
        for k, v in r["evidence"].items():
            if isinstance(v, str) and len(v) > 180:
                ev_short[k] = v[:177] + "..."
            else:
                ev_short[k] = v
        committed_items.append({**r, "evidence": ev_short})

    committed_payload = {**full_payload, "items": committed_items}
    (STATS_DIR / "v3-review.json").write_text(
        json.dumps(committed_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote review/v3_review_samples.json and docs/stats/v3-review.json ({len(reviewed_items)} items)")
    print("Overall:", dict(overall))
    for m, c in sorted(by_method_counts.items()):
        print(f"  {m}: {dict(c)}")
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
