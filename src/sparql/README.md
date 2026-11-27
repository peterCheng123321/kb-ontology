# 能力问题（CQ1–CQ7）

本目录是 7 条 SPARQL 1.1 查询。

- `CQ1_cross_jurisdiction_recall.rq`：美国召回对应的加拿大召回，区分硬键 `xjur_mfr_token` 与候选 `xjur_mmy_system_window`。
- `CQ2_dtc_make_context_disambiguation.rq`：同一故障码在不同厂语境下的定义，并标出跨品牌冲突。码为 P0300、P0420、P1326、B1234、C1250、P1009、C1391、C2200。
- `CQ3_component_to_mot_defect_stats.rq`：NHTSA 部件主类经 SKOS 对到英国 MOT 缺陷项，只取未抑制的 CR-V 2018 统计。
- `CQ4_component_to_can_vss.rq`：前向防撞、转向与制动部件对应的本田 CAN 报文，以及 COVESA VSS 与 W3C VSSo 对齐。
- `CQ5_dtc_to_obd_pid_vss.rq`：故障码 P0300 与 P0172 对应的 OBD 实时 PID（单位与公式）和 VSS 路径。
- `CQ6_ev_battery_fault_summary_vss.rq`：按品牌群体与故障标签汇总动力电池片段，并关联 Vehicle.Powertrain.TractionBattery 信号。
- `CQ7_multisource_closed_loop_chain.rq`：以投诉 ODINO 11407338 为锚，串联美加召回、故障码与维修、英国 MOT、本田 CAN 与 VSS。
