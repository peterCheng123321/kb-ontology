# 模块化 LinkML v3 多源售后知识库本体实验报告（第三阶段）

- **实验日期**：2026-11-25（Asia/Shanghai）
- **工具链实测版本**：Python `3.12.9`（`.venv`）、`linkml == 1.12.1`、`rdflib == 7.6.0`、`pyshacl == 0.40.2`、`pyoxigraph == 0.5.13`、OpenJDK `23.0.2`（满足 Java 21+）、`ROBOT 1.9.11`（内置 HermiT）。
- **合规与隐私红线**：仅摄入 A 级开放可商用源（B 级标准与非商用源严禁入 ABox）；零 VIN、零 MOT `vehicle_id`、零投诉叙述原文、零中文问诊对话原文；UK MOT 聚合单元计数 `< 5` 一律抑制（`insp:suppressed true` 且不输出 `insp:defectCount`）；全图无长度 `> 400` 的字面量（实测最大值 `350`）。
- **基线保护**：第一阶段 `schema/`、`shapes/`、`queries/`、`scripts/build_trial.py`、`scripts/run_queries_and_shacl.py`、`docs/PUBLIC-DATASETS-HF.md`、`docs/PUBLIC-DATASETS-EXTENDED.md` 均原样保留、零修改。

---

## 1. 结论先行

1. **模块化 LinkML v3 体系完整跑通**：按 [ONTOLOGY-TECH-STACK-v3.md](ONTOLOGY-TECH-STACK-v3.md) §4.1 在 `src/linkml/` 建立 `core / recall / diagnostics / inspection / signal / ev_battery` 六模块手写真源，经 `make gen` 生成 OWL、SHACL、JSON-LD context 与 JSON Schema 四类产物；经 ROBOT 1.9.11 检验 **100% 符合 OWL 2 DL 剖面**、**HermiT 推理一致**、**质量报告 `ERROR: 0`**；全图 **721,685 条 ABox 三元组**（约为第一阶段 `75,726` 条的 **9.5×**）通过完整 pySHACL 校验（生成形状 + 3 份手写补充形状，`conforms = True`）与隐私扫描（0 违例）。
2. **双轨扩展显著增强跨源闭环，但硬键仍极度稀疏（1.97% vs 98.03%）**：
   - **跨国召回**：本田 2018 切片上，美加厂内召回号硬键（`xjur_mfr_token`）实测为 **0**（加方燃油泵召回该字段留空，安全带/倒车/座椅召回则使用独立区域代码 `HN47`/`HP27`/`HQ62`）；引入 `xjur_mmy_system_window` 候选后精准找回 **7/7 组同源跨国召回**（其中 6 组发布日完全同日 `date_diff = 0d`，第 7 组为加方官方声明替代 `2023679` 的 `2024262`），人工字段级抽检 **7/7 `accepted`**。
   - **同码多厂多义**：合入 `CodesList` + `Wal33D` + `OBDex` 后，合规 DTC 池扩至 **12,420 个唯一码 / 37,752 条 `(code, makeContext, source)` 释义节点**。CQ2 实证：**`P1326`** 在 Wal33D 仅存 `VOLKSWAGEN` 释义，对本田上下文已自动打标 `mismatchFlag = true`、`score = 0.20` 并在抽检中 **`rejected`**；切片内 `P0300`/`P0420` 的 `AUDI` 冗余条目与 `C1870`（`OTHER`，空气悬架，本田 2018 无此配置）同样被精确拦截，证明用 `DtcDefinition` 分离品牌上下文的必要性。
   - **实车定期年检（UK MOT 2023）**：流式扫描 **42,216,722** 条年检结果与 **89,302,633** 条缺陷项（零落盘解压、零保留 `vehicle_id`），命中 **CR-V（2018 首次上牌）10,108 次年检**、**Accord 18 次年检**（验证英国市场雅阁 2018 极稀少），产出 **453 个聚合单元格**（`141` 个 `count >= 5` 可见、`312` 个 `< 5` 隐私抑制、`0` 个未知 RFR 丢弃），经 SKOS 挂载至 NHTSA 部件主类（CQ3 实测高频缺陷集中于轮胎磨损、刹车片厚度 `< 1.5mm`、雨刮与灯光，`30k–60k` 英里桶最密集）。
   - **车端总线与标准信号（opendbc + VSS v6.1 + VSSo）**：覆盖 `905` 个精选 VSS v6.1 信号（`116` 个自动 `skos:closeMatch` 到 W3C VSSo 类）、`80` 条 CAN 报文 / `753` 个 CAN 信号与 `132` 个 OBDex Mode 01/09 PID，打通「前向防撞/转向/制动 → 本田 Bosch CAN 报文 → VSS/VSSo」与「DTC → OBD-II PID（含换算公式/单位）→ VSS」两条工程链（CQ4 / CQ5）。
   - **轨 2 新能源动力电池（Figshare `30162841` 安全 CSV）**：完整聚合 3 个匿名车企品牌 **347 辆实车 EV / 700,582 条充电片段**（`55` 辆故障车 / `130,092` 故障片段，`292` 辆正常车 / `570,490` 正常片段），对齐至 `Vehicle.Powertrain.TractionBattery.*` 7 个核心信号（CQ6 实测总计 `700,582` 片段，零扇出膨胀）。
   - **七个能力问题（CQ1–CQ7）15/15 自动化断言全部通过**，单条 CR-V 2018 投诉 `ODINO 11407338` 实现六源闭环串联并输出 [figs/v3_chain_odino_11407338.png](../figs/v3_chain_odino_11407338.png)。

---

## 2. 第一阶段基线可复现重建与回归对照

为补足第一阶段缺失的切片脚本，本阶段新增 [scripts/build_slice_honda_2018.py](../scripts/build_slice_honda_2018.py) 与固化的中英部件词表 [src/mappings/zh_component_lexicon.yaml](../src/mappings/zh_component_lexicon.yaml)，在不改动第一阶段任何脚本与查询文件的前提下，由 [scripts/baseline_regression.py](../scripts/baseline_regression.py) 对重建后的第一阶段 ABox（`75,726` 三元组）跑 `shapes/basic.shacl.ttl`（`conforms = True`，`1.47s`）与只读 `queries/Q1..Q5.rq`（全部有结果：`Q1=3, Q2=4, Q3=12, Q4=8, Q5=2`）。完整 JSON 见 [docs/stats/v3-baseline-regression.json](stats/v3-baseline-regression.json)。

| 指标 | Phase 1 原值（`TRIAL-RESULTS.md`） | 本次重建值 | 差值（%） | 差异原因说明（不调参凑旧值） |
|---|---:|---:|---:|---|
| `VehicleModelYear` | 2 | 2 | 0 (0.00%) | 完全一致（CR-V / ACCORD 2018） |
| `Complaint`（按 `ODINO`） | 3,210 | 3,296 | +86 (+2.68%) | NHTSA `COMPLAINTS_RECEIVED_2025-2026.zip` 每日滚动新增 |
| `Recall` | 8 | 8 | 0 (0.00%) | 8 个召回活动号完全一致 |
| `Investigation` | 3 | 4 | +1 (+33.33%) | `ACCORD HYBRID` 归并入 `ACCORD` 带入全混动请愿 `DP22005`（其 `CAMPNO=22V063000` 非本田召回，硬边仍为 `0`） |
| `Component` | 32 | 27 | -5 (-15.62%) | 重建中英词表主类集合更收敛 |
| `DTC`（切片抽出） | 47 | 48 | +1 (+2.13%) | 新增投诉行中多抽出 1 个故障码 |
| `RepairStep` / `Part` | 46 / 77 | 46 / 77 | 0 / 0 (0.00%) | 与 MechanicDB 样本硬键完全一致 |
| `QaThread` | 301 | 301 | 0 (0.00%) | CR-V `94` + 雅阁 `207`，完全一致 |
| 硬连接边合计 | **123** | **123** | **0 (0.00%)** | `调查→召回=0`、`DTC→步骤=46`、`步骤→零件=77` |
| 投诉 → 召回候选 | 2,583 | 2,641 | +58 (+2.25%) | 随新增投诉线性增长 |
| 投诉 → 调查候选 | 1,516 | 1,805 | +289 (+19.06%) | 新增 `DP22005`（`ELECTRICAL SYSTEM`）带来候选增量 |
| 问诊 → 部件候选 | 554 | 731 | +177 (+31.95%) | 重建的 `zh_component_lexicon.yaml` 关键词覆盖更宽 |
| 投诉 → DTC 共现候选 | 253 | 258 | +5 (+1.98%) | 随新增投诉小幅增长 |

> 注：复现过程中观察到未改动的 `scripts/build_trial.py` 存在两处遗留工程问题（其内置 `Q1` 在 RDFLib 7.6.0 中出现慢连接，以及第 931 行 `ROOT` 未定义导致 PNG 写出前抛出 `NameError`）；但其第 689 行之前已完整落盘 `rdf/honda_2018_abox.ttl`、`data/honda-2018/stats.json` 与 `review/review_10.json`（10 条抽检仍为 `2 accepted / 2 rejected / 6 uncertain`）。按范围约定未改动第一阶段脚本，在 `Makefile` 中由 `scripts/baseline_regression.py` 承担只读回归检查。

---

## 3. v3 模块化 ABox 规模、实体与边比率

完整统计见 [docs/stats/v3-graph-stats.json](stats/v3-graph-stats.json)，模块与候选边分布总览见 [figs/v3_module_overview.png](../figs/v3_module_overview.png)。

### 3.1 六模块 Turtle 文件规模（`rdf/v3/`，不进 Git）

| 模块文件 | 三元组数 | 文件字节 | 核心内容 |
|---|---:|---:|---|
| `core.ttl` | 87,704 | 4,282,696 | 16 个 `DataSource`、2 MMY、29 `Component`、3,296 投诉、4 调查、301 问诊与基线候选边 |
| `recall.ttl` | 458 | 33,483 | 8 条 US 召回 + 8 条 CA 召回、`7` 条跨国窗口候选边、141 条召回原厂零件关联 |
| `diagnostics.ttl` | 537,418 | 29,650,153 | **12,420 `DTC`**、**37,752 `DtcDefinition`**、132 `ObdPid`、46 `RepairStep`、218 `Part`（77 MechanicDB + 141 召回原厂号） |
| `inspection.ttl` | 63,590 | 3,463,074 | UK MOT Class 4 **933 `MotItemGroup`**、**4,432 `MotDefectItem`**、129 方位、14 燃料、**453 聚合统计格**（141 可见 / 312 抑制） |
| `signal.ttl` | 20,067 | 1,086,624 | **905 `VehicleSignal`**（VSS v6.1，116 个对齐 VSSo）、**80 `CanMessage`**、**753 `CanSignal`**（Honda/BYD/Tesla） |
| `ev_battery.ttl` | 12,448 | 789,552 | 7 个学术数据集元数据（Figshare/Zenodo）+ Figshare `30162841` **347 `BatteryVehicleRef`** / **347 `BatterySnippetSummary`**（700,582 片段） |
| **合计** | **721,685** | **39,305,582** | 另导出 `sample_abox.ttl`（409 三元组）供 ROBOT HermiT 一致性检验 |

### 3.2 硬连接边 vs 候选连接边

| 类别 | 边方法 / 关系 | 数量 | 说明 |
|---|---|---:|---|
| **硬连接** | `dtc_to_repair_step` | 46 | MechanicDB 样本硬键 |
| **硬连接** | `repair_step_to_part` | 77 | MechanicDB 样本硬键 |
| **硬连接** | `investigation_to_recall_via_CAMPNO` | **0** | 本田 2018 切片调查无匹配本田召回号 |
| **硬连接** | `xjur_mfr_token`（本田 2018 切片） | **0** | 实证美加本田不共用厂内码；全库参考为 **4,461 CA ↔ 4,333 US**（不入切片图） |
| **硬边小计** | — | **123** | 占全部关系边 **1.97%**（硬/候选比 `0.0201`） |
| **基线候选** | `mmy_comp_head` / `mmy_comp_exact` | 2,591 / 50 | 投诉 → US 召回 |
| **基线候选** | `complaint_to_investigation` | 1,805 | 投诉 → NHTSA 调查 |
| **基线候选** | `qa_zh_lexicon` | 731 | 中文问诊 → 部件主类 |
| **基线候选** | `dtc_regex_cooccur` | 258 | 投诉叙述正则抽码共现（原文未入库） |
| **v3 新增候选** | `xjur_mmy_system_window` | **7** | 美加召回 MMY + 系统映射 + ±180 天窗 + 缺陷词元 Jaccard |
| **v3 新增候选** | `dtc_make_context` | **131** | 切片 DTC + `P1326` 对齐 `(code, makeContext, source)` 释义（含跨厂冲突标记） |
| **v3 新增候选** | `dtc_pid_subsystem` | **271** | 切片 DTC → SAE J2012 子系统段 → OBDex PID |
| **v3 新增候选** | `component_mot_group` | **30** | NHTSA 部件主类 ↔ UK MOT 顶层大类 SKOS 对照 |
| **v3 新增候选** | `component_can_message` | **37** | NHTSA 部件主类 ↔ 本田/BYD/Tesla `opendbc` CAN 报文 |
| **v3 新增候选** | `battery_fault_signal` | **220** | 55 辆故障 EV 摘要 → 4 个核心 VSS `TractionBattery` 信号 |
| **候选边小计** | — | **6,131** | 占全部关系边 **98.03%**（v3 新增 696 条跨源候选边） |

---

## 4. 能力问题（CQ1–CQ7）验收结果

全部 7 条 SPARQL 1.1 查询位于 `src/sparql/CQ1..CQ7.rq`，由 [scripts/v3_run_cq.py](../scripts/v3_run_cq.py) 在 `pyoxigraph`（`721,685` 三元组加载耗时 `1.11s`）上执行并自动断言，完整明细见 [docs/stats/v3-cq-results.json](stats/v3-cq-results.json)。**15/15 项自动化断言全部通过（`all_assertions_passed = true`）。**

| CQ | 查询文件 | 返回行数 | 耗时 | 关键实测结果与断言状态 |
|---|---|---:|---:|---|
| **CQ1** | `CQ1_cross_jurisdiction_recall.rq` | 7 | 0.005s | **4/4 PASS**：硬键 `0` 条；候选精准匹配 `18V629000↔2018500`、`20V314000↔2020236`、`20V771000↔2020611`、`23V158000↔2023127`、`23V858000↔2023679/2024262`、`26V332000↔2026251`，全部 `reviewStatus=accepted`。 |
| **CQ2** | `CQ2_dtc_make_context_disambiguation.rq` | 14 | 0.155s | **2/2 PASS**：`P1326` 仅命中 `VOLKSWAGEN` 且 `mismatch=true / score=0.2 / rejected`；`P0300`/`P0420` 清晰区分 `GENERIC`（3 源）与 `AUDI`（`mismatch=true`）；`B1234`/`C1250` 标 `OTHER` 冲突；`P1009`/`C1391`/`C2200` 显式标 `UNCOVERED`。 |
| **CQ3** | `CQ3_component_to_mot_defect_stats.rq` | 30 | 0.004s | **2/2 PASS**：覆盖 `TIRES`、`SERVICE BRAKES`、`VISIBILITY`、`EXTERIOR LIGHTING`、`ELECTRICAL SYSTEM` 五大主类；最高频为 CR-V 2018 `30k_60k` 英里桶胎纹 `<1.6mm`（`1,278` 次）与刹车片 `<1.5mm`（`636` 次）；**抑制格泄露检查 `leak_rows = 0`**，可见最小计数 `59`（全表可见格均 `>= 5`）。 |
| **CQ4** | `CQ4_component_to_can_vss.rq` | 19 | 0.001s | **2/2 PASS**：`FORWARD COLLISION AVOIDANCE`（`ACC_CONTROL` 16 信号、`ACC_HUD` 25 信号、`RADAR_HUD` 15 信号）、`STEERING`（`STEERING_CONTROL` 8 信号、`STEER_STATUS` 7 信号）、`SERVICE BRAKES`（`BRAKE_MODULE` 4 信号、`VSA_STATUS` 8 信号等）全部覆盖，其中 **13 行精确携带 `https://github.com/w3c/vsso#...` 对齐**。 |
| **CQ5** | `CQ5_dtc_to_obd_pid_vss.rq` | 18 | 0.001s | **2/2 PASS**：`P0300`（8 个 PID）与 `P0172`（10 个 PID）返回单位、换算公式（17 行含公式，如 `01-0C: (256*A+B)/4 rpm`、`01-06: 100/128*A-100 %`）及 6 条准确 VSS v6.1 路径（如 `EngineCoolant.Temperature`、`MAP`、`MAF`、`TPS`、`Speed`）。 |
| **CQ6** | `CQ6_ev_battery_fault_summary_vss.rq` | 6 | 0.006s | **2/2 PASS**：完整覆盖 `battery_brand1`（30 故障车/17,031 片段；168 正常车/459,708 片段）、`battery_brand2`（16 故障车/111,287 片段；33 正常车/82,958 片段）、`battery_brand3`（9 故障车/1,774 片段；91 正常车/27,824 片段），**精准合计 `700,582` 片段**，每组均对齐 **7 个 `Vehicle.Powertrain.TractionBattery.*` 信号**。 |
| **CQ7** | `CQ7_multisource_closed_loop_chain.rq` | 32 | 0.003s | **1/1 PASS**：单条 CR-V 2018 投诉 `11407338` 同时串联全部 4 类跨源跳（US/CA 召回 `23V858000↔2023679/2024262` + `P0172/P0300/P0301` 维修步骤零件 + UK MOT 燃油/排放 `RFR_31885/31938/31940` 非抑制频次 + 本田 `ACC_CONTROL`/`ENGINE_DATA` CAN 与 VSS 信号）。 |

六源闭环示意图见 [figs/v3_chain_odino_11407338.png](../figs/v3_chain_odino_11407338.png)。

---

## 5. 新增候选边字段级人工抽检汇总（57 条）

依据审核协议，每类新增跨源候选边抽取 10 条（`xjur_mmy_system_window` 共 7 条全审），**仅凭官方文本、标准词表与结构化元数据**判定并回写进图中 `core:reviewStatus` 与 `core:note`。完整抽检表见 [docs/stats/v3-review.json](stats/v3-review.json)（供业务/架构评审人抽查）。

| 候选边类型 | 抽检数 | `accepted` | `rejected` | `uncertain` | 核心审核发现 |
|---|---:|---:|---:|---:|---|
| `xjur_mmy_system_window` | 7 | 7 | 0 | 0 | 6 对同日发布 + 1 对加方替代公告，官方摘要主题完全一致 |
| `dtc_make_context` | 10 | 4 | **6** | 0 | 精准拒掉 `P1326(VW)`、`P0300/P0301(AUDI)`、`B1234/C1250/C1870(OTHER)` 跨厂错配；通用 SAE 码通过 |
| `component_mot_group` | 10 | 7 | 0 | 3 | 6 个 `exactMatch` 清晰；`ELECTRICAL SYSTEM`/`FUEL SYSTEM`/`ENGINE` 对应 MOT 20158/20385 偏宽或偏窄，标 `uncertain` |
| `component_can_message` | 10 | 8 | 0 | 2 | ADAS/转向/制动/安全带报文精准；`ENGINE_DATA→FUEL SYSTEM` 与 `BSM→BACK OVER PREVENTION` 属间接关联 |
| `dtc_pid_subsystem` | 10 | 8 | 0 | 2 | 动力总成 `P0300`/`P0172` 对应 PID 准确；车身 `B0020`/底盘 `C0023` 无法仅靠 Mode 01 诊断，标 `uncertain` |
| `battery_fault_signal` | 10 | 8 | 0 | 2 | SOC/单体电压/最高温与论文任务一致；SOH 仅靠里程间接代理且纯 CSV 无容量标定，标 `uncertain` |
| **合计** | **57** | **42** | **6** | **9** | **不放水、不伪造确认；高风险跨厂错配 100% 识别并拦截** |

---

## 6. SHACL 校验、夹具测试与 ROBOT（OWL 2 DL/RL + HermiT）结论

### 6.1 pySHACL + 正反例夹具 + 隐私扫描（[docs/stats/v3-validation.json](stats/v3-validation.json)）
- **全图 pySHACL**：对 `721,685` 条 ABox 三元组，合并 `gen/shacl/poc-kb.shacl.ttl`（`2,234` 三元组）与 `src/shacl/extras/` 3 份手写形状（`privacy.shacl.ttl`、`stat-suppression.shacl.ttl`、`candidate-link.shacl.ttl`，合计 `2,272` 形状三元组），实测 **`conforms = True`**（解析 `16.45s`，校验 `125.57s`）。
- **夹具单元测试（`pytest tests -q`）**：**`6 passed in 0.55s`** — 全模块正例 `all_modules_valid.ttl` 通过；5 份反例（17 位 VIN 注入、禁用 `cdescr` 谓词、MOT `count=3` 未抑制、`CandidateLink` 分数 `1.50` 越界、`DtcDefinition` 缺必填 `makeContext`）全部准确失败并命中预期形状消息。
- **全图隐私与卫生扫描**：`vin_17char_hits = 0`、`forbidden_predicate_hits = 0`、`overlong_literals_gt_400 = 0`、`max_literal_length = 350`、`stats_json_privacy_hits = []`。

### 6.2 ROBOT 1.9.11 剖面校验与 HermiT 推理（`ci/robot.sh`）
- **OWL 2 DL 剖面（发布阻断门禁）**：**PASS**（`OWL 2 DL Profile Report: [Ontology and imports closure in profile]`）。通过合并 `src/linkml/owl_annotations.ttl`（补齐 LinkML 生成器未声明的 `dcterms`/`skos`/`linkml` 注解属性）并将 `core:score` 数值范围约束移入 SHACL extras，彻底修复了第一阶段 `honda_2018_trial.owl.ttl` 上暴露的 DL 注解属性缺失与 HermiT `xsd:float`/`xsd:double` facet 崩溃问题。
- **OWL 2 RL 剖面（信息记录，非阻断）**：记录 `218` 条违例（`gen/robot/rl-profile.txt`），原因全部为 LinkML `gen-owl` 默认生成的 `DataMinCardinality`/`ObjectMinCardinality` 及枚举 `ObjectUnionOf` 公理超出 OWL 2 RL 规则子集——符合 [ONTOLOGY-TECH-STACK-v3.md](ONTOLOGY-TECH-STACK-v3.md) §2.4「发布期跑 DL/HermiT、运行期在 Fuseki 侧仅启用 RL 规则子集」的分工预期。
- **HermiT 一致性与分类**：TBox（`gen/robot/merged-tbox.ttl`）与 TBox + 409 三元组跨模块抽样 ABox（`rdf/v3/sample_abox.ttl`）均 **CONSISTENT（退出码 0）**。
  - **重要工程观察**：合并抽样 ABox 时，OWL API 对 11 个枚举属性输出了 `OWLAnnotationPropertyTransformer` 告警（`OWLLiteralImplString cannot be cast to IRI`）。原因是 LinkML `gen-owl` 将枚举生成为 `owl:ObjectProperty`（值域为枚举个体 IRI），而 LinkML `gen-shacl` 将同一枚举生成为 `xsd:string` 字面量约束（`sh:in ("accepted" ...)`）。本实验遵循 SHACL 互操作约定在 ABox 输出字符串字面量，HermiT 对其余全部类/对象属性公理正常完成一致性检验；若后续需要在 OWL 层对枚举做 DL 推理，需在发布管线增设枚举字符串→个体 IRI 转换步。
- **ROBOT 质量报告（`gen/robot/report.tsv`）**：**`ERROR: 0`**（`WARN: 238` 主要为 OBO 规范检查 `IAO:0000115`，因 LinkML 使用 `skos:definition`；`INFO: 8`）。

### 6.3 生成物复现核对表（`gen/` 不进 Git，可由 `make gen` 确定性复现）

| 生成产物 | 字节数 | 三元组数 | SHA-256 |
|---|---:|---:|---|
| `gen/owl/poc-kb.owl.ttl` | 120,859 | 3,438 | `d657e3f54a38fe99ab4c20d5624b677e05ff146bca2ae4f9e8a79e848e403062` |
| `gen/shacl/poc-kb.shacl.ttl` | 68,123 | 2,234 | `295b1d0b5587e923f4be5e7fe1b2c7fc405064081f9c679880f0ed9a1de032bd` |
| `gen/jsonld/poc-kb.context.jsonld` | 16,213 | — | `b26a51db164011ca6dc13c547d9e6d5223a28c32ec05d5358b3cd0cf9a6839df` |
| `gen/jsonschema/poc-kb.schema.json` | 68,409 | — | `80fafbdf4f4a9b003debfdca2fe09f2fe1b58f4c0c57579cf826347e094de709` |

---

## 7. 明确断开或很弱的关系（坦白边界，不夸大效果）

1. **硬连接依然极少（仅占 1.97%）**：跨平台补充 8 类 A 级新源后，本田 2018 切片内的官方硬键仍是 `123` 条（全来自 MechanicDB 样本），调查→召回硬键 `0` 条，美加跨国厂内号硬键在本田 2018 切片上亦为 `0` 条（尽管全库级可打通 `4,461 ↔ 4,333` 条）。业务演示必须继续坚持「默认只展示硬键 + 抽检 `accepted` 候选」。
2. **厂标 DTC 缺口仍在**：三库合并后扩至 `12,420` 码，但本田 2018 切片中仍有 `P1009`、`P16E8`、`P04F1`、`C1C01–C1C04` 等厂标码及 NHTSA Top-20 的 `C1391`、`C2200` 在全部合规开源库中均无公开定义（CQ2 显式标 `UNCOVERED`）。
3. **英国 MOT 车型与市场差异**：UK MOT 2023 对 CR-V 2018 样本充沛（`10,108` 次），但 Accord 2018 仅 `18` 次测试，且 `312/453`（68.9%）的细粒度单元格因 `< 5` 被隐私抑制；此外 MOT 检验偏重轮胎/刹车/灯光/视野等法定安检项，对燃油泵内部故障或 ADAS 软件误触发并无直接检出项。
4. **OBD-II Mode 01 PID 仅覆盖排放与动力总成**：对 `B`（车身/安全气囊）和 `C`（底盘/ABS）故障码，通用 OBD-II Mode 01 无法读取真实传感器阻值或轮速细节，需依赖主机厂私有 UDS DID / ODX 定义。
5. **Figshare `30162841` 原始波形安全边界**：实测 `30162841` 压缩包中安全可读的 28 份纯 CSV 仅含 `car / label / mileage / charge_segment` 元数据与片段级故障标签，不含单体电压/温度原始时序曲线（原始波形位于 `23659323` 的 `.pkl` 序列化文件中，出于反序列化代码执行安全考虑本次未加载，故 `evb:BatterySnippetSummary` 中 `socMin/cellVoltageMin/cellTempMax` 保留为 Schema 就绪槽位而未填充伪造数值）。
6. **Jena Fuseki 6.3.0 运行时加载（P8 可选步骤）未在本次执行**：CQ1–CQ7 全部在 `pyoxigraph` 内存三元组库上复现；标准 Turtle 产物已就绪，后续可直接用 `tdb2.tdbloader` 载入 Fuseki TDB2 验证零改动迁移。

---

## 8. 相对第一阶段（v1）的模式演进清单

| 变化项 | v1（`schema/honda_2018_trial.yaml`） | v3（`src/linkml/*.yaml`） | 数据实证驱动依据 |
|---|---|---|---|
| 目录与模块化 | 单文件 `schema/honda_2018_trial.yaml` | 6 领域模块 + `prefixes` / `metadata` / `catalog` | 对齐技术栈 v3.0 目标布局，隔离轨 1/轨 2 演进 |
| `DTC` 建模 | 单一 `DTC.description` 字符串 | 拆分为 `DTC` + `DtcDefinition(definesCode, makeContext, fromSource)` | 实证 `P1326`（VW vs 现代/起亚）及 `P0300`（AUDI vs GENERIC）同码多厂多义 |
| `Recall` 建模 | 单国 `Recall(campno)` | `JurisdictionRecall(jurisdiction, officialRecallId, manufacturerRecallNumber[], systemType, replacesRecallId)` | 实证美加本田不共用厂内召回号，且存在跨国替代公告 |
| `QaThread` 声明 | ABox 写入但 LinkML schema 漏声明 | 在 `core.yaml` 正式声明并受生成 SHACL 约束 | 消除 v1 隐式类型 |
| `CandidateLink.score` | Schema 写 `float` 导致 HermiT 报错，ABox 用 `decimal` | 统一为 `xsd:decimal`，`[0.0, 1.0]` 移入 `src/shacl/extras/candidate-link.shacl.ttl` | 根治 ROBOT/HermiT datatype facet 报错并消除 v1 类型分裂 |
| 新增领域类 | 无 | `DataSource`、`ObdPid`、`MotItemGroup/DefectItem/Location/FuelType/InspectionDefectStat`、`VehicleSignal/CanMessage/CanSignal`、`BatteryDataset/VehicleRef/SnippetSummary` | 100% 由第二/三阶段实测 A 级数据推导，零空想预置 |
