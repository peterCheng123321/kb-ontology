# 能力问题（CQ1–CQ7）SPARQL 查询集

依据「数据优先」范式，以下 7 条标准 SPARQL 1.1 查询均基于第二/三阶段实测数据编写，由 `scripts/v3_run_cq.py` 在合并后的 `rdf/v3/*.ttl` 上执行并自动断言，输出写入 `docs/stats/v3-cq-results.json`：

- `CQ1_cross_jurisdiction_recall.rq`：美加跨国召回互链（区分 `xjur_mfr_token` 硬键与 `xjur_mmy_system_window` 候选）。
- `CQ2_dtc_make_context_disambiguation.rq`：DTC 同码多厂多义与跨品牌冲突标识（`P0300` / `P0420` / `P1326` / `B1234` / `C1250` / `P1009` / `C1391` / `C2200`）。
- `CQ3_component_to_mot_defect_stats.rq`：NHTSA 部件主类经 SKOS 对齐到英国 DVSA MOT 2023 年 CR-V 2018 聚合缺陷频次（仅返回非抑制格，`k<5` 格受 SHACL 保护不泄露计数）。
- `CQ4_component_to_can_vss.rq`：前向防撞 / 转向 / 制动部件 → 本田 `opendbc` CAN 报文信号 → COVESA VSS v6.1 与 W3C VSSo 对齐。
- `CQ5_dtc_to_obd_pid_vss.rq`：高频故障码（`P0300`、`P0172`）→ SAE J2012 子系统映射 → OBDex 实时 PID（单位/公式）→ VSS 路径。
- `CQ6_ev_battery_fault_summary_vss.rq`：轨 2 新能源动力电池（Figshare `30162841` 347 车 / 70 万充电片段）按品牌群体与故障标签聚合统计，并关联 `Vehicle.Powertrain.TractionBattery.*` 信号。
- `CQ7_multisource_closed_loop_chain.rq`：单条 CR-V 2018 投诉（`ODINO 11407338`）六源闭环串联（US/CA 召回 + 多厂标 DTC + 维修步骤/零件 + 英国 MOT 频次 + 本田 CAN 报文/VSS）。
