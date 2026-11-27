# 跨平台公开数据集扩展核查与双轨实测报告（第二阶段）

- **日期**：2026-11-25（Asia/Shanghai）
- **定位**：在第一阶段 Hugging Face + 美国 NHTSA 核查（见 [PUBLIC-DATASETS-HF.md](PUBLIC-DATASETS-HF.md)）和本田 CR-V / 雅阁 2018 试验（[TRIAL-RESULTS.md](TRIAL-RESULTS.md)、[STEP2-RESULTS.md](STEP2-RESULTS.md)）基础上，面向全球开放阵地扩展调研，重点补齐**保修/年检维保历史、大规模通用与厂标 DTC、跨国召回互链、新能源三电（BMS）实车故障、车端标准信号与 CAN 总线、以及中文售后与结构化维修路径**。
- **调研阵地覆盖**：
  1. **多国政府与监管开放平台**：加拿大 Transport Canada（VRDB）、英国 DVSA（MOT 年检）、欧盟 Safety Gate（RAPEX）、日本国土交通省（MLIT）、中国国家级及京/沪/深地方政务与交通标准源；
  2. **GitHub 行业标准与开源工程仓**：COVESA VSS v6.1、W3C VSSo、`commaai/opendbc`、`Wal33D/dtc-database`、`foerbsnavi/OBDex` 等；
  3. **学术与科研数据仓储**：Figshare REST API、Zenodo（via DataCite REST API）、国家基础学科公共科学数据中心（NBSDC/CSTR）、ScienceDB、Harvard Dataverse；
  4. **国内外数据与竞赛社区**：Kaggle、阿里天池（Tianchi）、和鲸社区（Heywhale）、百度飞桨 AI Studio、DataFountain、OpenDataLab（明确排除自动驾驶纯视觉感知集）。
- **合规与隐私红线**：
  - **A/B 双层分级**：**A 级**（开放可商用许可：`Public Domain` / `OGL` / `OGL-Canada` / `CC0-1.0` / `MIT` / `Apache-2.0` / `MPL-2.0` / `CC-BY-4.0`）方可作为 POC 数据与分发依据（含需免费注册/Token 下载者另注）；**B 级**（`CC-BY-NC`、仅限在线分析/竞赛专用协议、申请制科研库、或无批量下载的行业标准数据元）单独隔离，**仅用于推导本体字段与关系形态，严禁进入对外 POC 数据集**。
  - **排除原则**：无许可证仓库、已关停赛题、纯商业付费墙、强传染性或跨行业误标数据（如家电保修伪装成汽车保修）、以及存在爬虫/版权/reCAPTCHA 门禁阻断的通道，均如实列明不纳入 A 级可用清单。
  - **零 PII 原则**：本仓库与统计 JSON（[extended-probe-stats.json](stats/extended-probe-stats.json)）不存放第三方原始数据，不输出任何 VIN、车主/操作人信息或长段投诉/问诊原文。

---

## 0. 新增 A 级免登录直链速查表（2026-11-25 实测 HTTP 200）

下列地址均由 [probe_extended_datasets.py](../scripts/probe_extended_datasets.py) 在本次环境中完成真实 HTTP 核验与本地缓存剖析（存本地 `data/raw/extended/`，已列入 `.gitignore`）。

| 数据源 | 直接下载 / API 链接 | 实测大小 / 状态 | 许可证 | 核心用途 |
|---|---|---|---|---|
| 加拿大 Transport Canada VRDB 全量 | https://opendatatc.tc.canada.ca/vrdb_full_monthly.csv | 186.7 MB（134,329 行），HTTP 200 | Open Government Licence - Canada | 跨国召回、`MANUFACTURER_RECALL_NO_TXT` 厂内号互链、`HIGH VOLTAGE` 等分类 |
| 英国 DVSA MOT 查找字典 | https://data.dft.gov.uk/anonymised-mot-test/lookup.zip | 254 KB（6 张查找表），HTTP 200 | UK Open Government Licence (OGL) | 实车定期年检缺陷树（934 节点 / 4,432 项）、严重度分级、14 种燃料枚举 |
| 英国 DVSA MOT 2023 年度数据（参考大包） | https://data.dft.gov.uk/anonymised-mot-test/test_data/dft_test_result_2023.zip （及 `dft_test_item_2023.zip`） | 1.19 GB / 460 MB，HTTP 200 | UK Open Government Licence (OGL) | 实车里程、车龄、故障检出项绑定关系（按需离线拉取） |
| GitHub `Wal33D/dtc-database` | https://raw.githubusercontent.com/Wal33D/dtc-database/main/data/dtc_codes.db | 3.26 MB SQLite（18,805 行 / 12,128 码），HTTP 200 | MIT | 通用 + **33 个主机厂**（含 Honda 94 条）厂标 DTC 扩展库 |
| GitHub `foerbsnavi/OBDex` | https://github.com/foerbsnavi/OBDex （`data/generic/*.yaml` & `data/pids/*.yaml`） | ~32.8 MB YAML（9,533 码 + 132 PIDs），HTTP 200 | CC0-1.0（数据）/ MIT（代码） | 100% 带外部来源溯源的 SAE J2012 审校码表 + Mode 01/09 PID 换算公式 |
| COVESA VSS v6.1 标准信号表 | https://github.com/COVESA/vehicle_signal_specification/releases/download/v6.1/vss.csv | 342 KB（1,737 个标准节点），HTTP 200 | MPL-2.0 | 三电（`TractionBattery` / `ElectricMotor`）、ADAS、诊断信号标准词表 |
| W3C VSSo 车辆信号本体 | https://raw.githubusercontent.com/w3c/vsso/gh-pages/spec/vsso-core.ttl （及 `vss_rel_2.2.ttl`） | 9.2 KB / 215.5 KB Turtle，HTTP 200 | CC-BY-4.0（本体）/ Apache-2.0（代码） | 基于 SOSA/SSN 的标准 OWL/Turtle 车辆信号观测对齐模板 |
| `commaai/opendbc` 实车 CAN DBC | https://github.com/commaai/opendbc （`opendbc/dbc/` 及 `generator/honda/`） | 单文件 0.4–24 KB，HTTP 200 | MIT | 本田 Bosch ADAS、比亚迪 ATTO3、特斯拉 Model 3 实车总线信号名 |
| Figshare `EVBattery`（清华团队） | https://figshare.com/articles/dataset/EVBattery_A_Large-Scale_Electric_Vehicle_Dataset_for_Battery_Health_and_Capacity_Estimation/23301881 （REST API ID: `23301881`） | 1.41 GB（3 压缩包），API 200 | CC-BY-4.0 | 数百辆实车多年充电记录 + 电池健康/容量双标注（轨 2） |
| Figshare 动力电池真实故障集（含预处理轻量版） | https://figshare.com/articles/dataset/Realistic_fault_detection_of_Li-ion_battery_via_dynamical_deep_learning_approach/23659323 （预处理：`30162841`） | 1.48 GB / 预处理版 52.2 MB，API 200 | CC-BY-4.0 | 347 辆实车 69 万+充电片段与电池异常检测（轨 2） |
| Zenodo 实车 BMS 云端故障集 | https://zenodo.org/doi/10.5281/zenodo.10656500 （另有 `19006180`、`18328700`） | DataCite API 200 | CC-BY-4.0 | 515 辆实车 1,820 万条记录：热失控、内短路、漏液、过老化故障标签（轨 2） |
| Zenodo 结构化汽车故障诊断集 | https://zenodo.org/doi/10.5281/zenodo.15626055 | DataCite API 200 | CC-BY-4.0 | 故障—症状—分步诊断流程图—处置结果 JSON（补齐维修决策链） |

> 注：Zenodo 页面及文件直链目前对自动化爬虫存在 WAF 403 拦截，但全部 DOI 元数据可通过开放的 `https://api.datacite.org/dois/{doi}` 公开核实，人工经浏览器访问下载正常。

---

## 1. 跨平台 Top 推荐榜（面向售后知识库本体补盲）

按「修补第一阶段核心断链的能力、许可证合规性、字段结构清晰度、实测可得性」排序：

1. **GitHub `Wal33D/dtc-database`（MIT）+ `foerbsnavi/OBDex`（CC0-1.0）**：直接打破第一阶段只有 9,414 个通用码的僵局，将合规可用 DTC 池扩大至 **12,412 个唯一码（+31.85%）**，新增 **33 个主机厂的厂标码**（含 Honda 94 条）与 **132 个带有物理换算公式的 Mode 01/09 PIDs**，直接攻克此前 NHTSA Top 1 未覆盖高频码 `P1326`（580 行）。
2. **加拿大 Transport Canada VRDB（OGL-Canada）**：全球少有提供月更/日更 **186.7 MB 全量 CSV** 且完全可商用的政府召回库，71.83% 的记录自带 `MANUFACTURER_RECALL_NO_TXT`。实测全局与美国 NHTSA 2010+ 打通 **4,461 条加拿大召回 ↔ 4,333 条美国召回**硬键连接。
3. **英国 DVSA MOT Testing Data（UK OGL）**：弥补了全球公开库普遍缺乏「实车检验里程 × 车龄 × 零部件缺陷」的致命空白。254 KB 的 `lookup.zip` 即包含 **5 层 934 节点**的乘用车检查树、**4,432 条法定缺陷定义**（带 `Minor/Major/Dangerous` 严重度）、**129 个三维空间位置**和 **14 种燃料（含纯电/混动/氢燃料电池）**。
4. **COVESA VSS v6.1（MPL-2.0）+ W3C VSSo（CC-BY-4.0）+ `commaai/opendbc`（MIT）**：一套可直接映射到 LinkML/OWL/Turtle 技术栈的车端信号参考体系。VSS v6.1 提供 **1,737 个标准化车端节点**（包含 **96 个动力电池与充电信号**、**84 个电驱信号**、**72 个 ADAS 信号**）；`opendbc` 提供 Honda Bosch ADAS/雷达、BYD Atto3、Tesla Model 3 实车 CAN 报文/信号名，把「抽象部件名」接地到真实电控总线信号。
5. **Zenodo 实车 BMS 云端故障集（`10656500` / `19006180` / `18328700`，CC-BY-4.0）与 Figshare `EVBattery` / 充电异常集（`23301881` / `23659323` / `30162841`，CC-BY-4.0）**：在车企内部新能源三电故障日志未脱敏前，最可靠的实车采集 BMS 数据底座，涵盖热失控、内短路、微短路、电解液泄漏、容量严重衰减及充电异常标签，直接支撑本体中新能源三电异常观测槽位推导。
6. **Zenodo 结构化汽车故障与维修流集（`10.5281/zenodo.15626055`，CC-BY-4.0）**：补充第一阶段 `MechanicDB` 仅靠 DTC 驱动维修步骤的不足，提供「无故障码前提下的现象/症状 → 分步排查流程图 → 最终处置结果」结构化 JSON。
7. **（B 级 Schema 黄金参照）交通部行业标准 JT/T 1132.3《汽车维修电子健康档案系统 第 3 部分：数据元》+ 和鲸 SHEVDC 运行数据 + 百度 AI Studio 汽车大师原集（CC0）**：中国本土真实维修结算工单字段标准（维修单号、VIN 脱敏锚点、维修项目与工时、配件编码与数量、结算金额、故障描述），直接定义国内主机厂/4S 店工单接入的规范槽位。

---

## 2. A 级（可商用 / 可入对外 POC 库）已核实清单

> 注：本表收录明确采用开放商用许可的数据源。标注「免登录直链」的可由脚本自动下载；标注「需免费账号/Token」的受平台防刷机制或 API 认证约束，需使用者自行注册后凭合法 Token 获取，禁止自动化绕过。

### 2.1 多国政府与监管开放源

| 名称 | 位置 | 许可证 | 获取方式 | 实测规模与结构 | 核心字段 | 对本体的补盲价值 |
|---|---|---|---|---|---|---|
| **加拿大 Transport Canada VRDB** | [Open Canada](https://open.canada.ca/data/en/dataset/1ec92326-47ef-4110-b7ca-959fab03f96d) / [直链 CSV](https://opendatatc.tc.canada.ca/vrdb_full_monthly.csv) | Open Government Licence - Canada | **免登录直链**（HTTP 200）；另提供 v1.3 JSON API | **134,329 行**、16,479 个召回号、52,089 个 MMY；英法双语；14/15 列填充率 100% | `RECALL_NUMBER_NUM, YEAR, MANUFACTURER_RECALL_NO_TXT, MAKE_NAME_NM, MODEL_NAME_NM, UNIT_AFFECTED_NBR, SYSTEM_TYPE_ETXT, CATEGORY_ETXT, COMMENT_ETXT, RECALL_DATE_DTE` | 跨国召回互链；71.83% 含厂内号；独立列出 `HIGH VOLTAGE`（701 行）等高压三电类 |
| **英国 DVSA MOT Testing Data** | [data.gov.uk](https://data.gov.uk/dataset/e3939ef8-30c7-4ca8-9c7c-ad9475cc9b2f/anonymised-mot-tests-and-results) / [字典 lookup.zip](https://data.dft.gov.uk/anonymised-mot-test/lookup.zip) | UK Open Government Licence (OGL) | **免登录直链**（需用 GET，CDN 禁用 HEAD 405） | 字典 254 KB（6 表）；2023 年度结果 1.19 GB + 缺陷项 460 MB；Class 4 乘用车 934 树节点 / 4,432 条 RFR | 结果：`test_id, vehicle_id, test_date, test_result, test_mileage, fuel_type, first_use_date`；缺陷：`rfr_id, test_item_id, rfr_deficiency_category, location_id` | 填补**实车里程—车龄—部件缺陷—严重度—三维位置**关系；含 `EL/HY/FC` 新能源燃料码 |
| **欧盟 Safety Gate (RAPEX) Alerts** | [data.europa.eu](https://data.europa.eu/data/datasets/rapex-rapid-alert-system-non-food) / [门户检索](https://ec.europa.eu/safety-gate-alerts/) | 欧盟委员会复用政策（CC-BY-4.0 等效，须署名来源） | **Web 导出 / 周报 XML 订阅**（无一键全量历史大 CSV；部分 API 端口需交互会话） | 按周发布非食品高危产品通告，含 `Motor vehicles` 大类 | 品牌、车型/EC 型式认证号、生产批期、危害分类（火灾/伤害等）、采取措施（召回/停售） | 补齐欧系与进口车型缺陷公告及 EC 型式认证编号槽位；不作批量结构化主键依赖 |
| **日本国土交通省 MLIT 不具合・リコール** | [MLIT Recall Portal](https://www.mlit.go.jp/jidosha/carinf/rcl/index.html) / [公表資料](https://www.mlit.go.jp/jidosha/carinf/rcl/data.html) | 政府公共数据利用条款 1.0（兼容 CC-BY-4.0） | **Web 条件检索后页面导出 CSV**（旧版 `opn.html` 等静态页已 404，仅保留交互检索与年报 PDF） | 含召回届出与车主/维修厂不具合申报列表（用户申报含未核实因素） | 车名、型式、不具合装置分类、现象摘要、申告状况、届出编号 | 日系车型原生缺陷术语对照；因无批量平面下载直链，不入自动化拉取脚本 |

### 2.2 GitHub 行业标准、CAN 总线与开源诊断仓

| 名称 | 仓库地址 | 许可证 | 获取方式 | 实测规模与结构 | 核心字段 | 对本体的补盲价值 |
|---|---|---|---|---|---|---|
| **Wal33D/dtc-database** | https://github.com/Wal33D/dtc-database | **MIT** | **免登录直链**（SQLite 3.26 MB） | **18,805 行**（P 14,821 / B 1,465 / C 985 / U 1,534），**12,128 唯一码**；通用 9,415 + **33 个厂商**（Honda 94、VW 528 等） | `code, manufacturer, description, type, locale, is_generic, source_file` | 目前许可最清晰的「通用 + 多厂标」开源码库，证明 `(code, manufacturer)` 复合建模必要性 |
| **foerbsnavi/OBDex** | https://github.com/foerbsnavi/OBDex | **CC0-1.0**（数据）/ **MIT**（代码） | **免登录直链**（YAML） | **9,533 条** SAE J2012 通用码（100% 带 `sources` 溯源与英德双语）+ **132 个 Mode 01/09 PID** | `code, category, title.{en,de}, description.{en,de}, sources`；PID 含 `bytes, formula, unit, range` | 质量极高的有溯源通用 DTC + OBD 实况 PID 计算与单位标准槽位 |
| **COVESA VSS v6.1** | https://github.com/COVESA/vehicle_signal_specification | **MPL-2.0** | **免登录直链**（Release `v6.1/vss.csv`, 342 KB） | **1,737 个标准节点**（355 branch / 164 attribute / 575 sensor / 643 actuator） | `Signal, Type, DataType, Deprecated, Unit, Min, Max, Desc, Allowed, Default` | 补足三电（`TractionBattery`+`Charging` 96 项、`ElectricMotor` 84 项）、ADAS（72 项）与诊断信号规范名 |
| **W3C VSSo** | https://github.com/w3c/vsso | **CC-BY-4.0**（本体）/ **Apache-2.0**（代码） | **免登录直链**（`gh-pages/spec/*.ttl`） | `vsso-core.ttl`（9.2 KB，8 核心类）+ `vss_rel_2.2.ttl`（215.5 KB，508 类） | 基于 W3C SOSA/SSN 的 `Branch / ObservableSignal / ActuatableSignal` | 与本项目 LinkML → Turtle → OWL 2 RL 栈天然兼容的语义网对齐模板 |
| **commaai/opendbc** | https://github.com/commaai/opendbc | **MIT** | **免登录直链**（`opendbc/dbc/`） | 含本田（`_bosch_2018.dbc` 20 帧/166 信号、`_honda_common.dbc` 23 帧/160 信号）、BYD Atto3（14 帧/103 信号）、Tesla Model 3 / Powertrain 等 | CAN DBC 标准定义：`BO_`（Frame ID/Name）、`SG_`（Signal Name/Scale/Offset/Unit） | 实车总线信号对齐桥：可把制动/AEB/EPS 转向/电池报文映射到 NHTSA 部件路径 |

### 2.3 学术仓储（Figshare / Zenodo）开放数据集

| 名称 | 链接 / DOI | 许可证 | 获取方式 | 实测规模与结构 | 核心内容与故障覆盖 | 对本体的补盲价值 |
|---|---|---|---|---|---|---|
| **EVBattery（清华团队）** | https://figshare.com/articles/dataset/EVBattery_A_Large-Scale_Electric_Vehicle_Dataset_for_Battery_Health_and_Capacity_Estimation/23301881 （`10.6084/m9.figshare.23301881`） | **CC-BY-4.0** | **免登录直链 / Figshare API** | **1.41 GB**（3 个压缩包），3 家主机厂数百辆实车跨多年充电记录 | 实车充电电压/电流/温度/SOC 时序 + **电池健康度（SOH）** 与 **容量估算** 双标签 | 轨 2 核心基石：推导动力电池健康衰减与多厂异构充电特征槽位 |
| **Realistic Li-ion Battery Fault Detection** | https://figshare.com/articles/dataset/Realistic_fault_detection_of_Li-ion_battery_via_dynamical_deep_learning_approach/23659323 （预处理轻量版：[30162841](https://figshare.com/articles/dataset/Multimodal_Deep_Learning_Framework_for_Electric_Vehicle_Battery_Fault_Diagnosis_via_Spectrogram_Time_Series_Fusion_preprocessed_data_/30162841)） | **CC-BY-4.0** | **免登录直链 / Figshare API** | 原包 **1.48 GB**（3 品牌，347 辆实车，69 万+充电片段）；预处理版 **52.2 MB** | 实车充电工况下电芯/模组异常与故障检测标注 | 轨 2 核心：直接看清实车充电异常检测特征与标签粒度的最佳轻量样本 |
| **Model-Constrained Online Battery Fault Diagnosis** | https://zenodo.org/doi/10.5281/zenodo.10656500 | **CC-BY-4.0** | **浏览器访问下载**（API 元数据通过 DataCite 200 核实；自动化爬虫受 WAF 403） | 515 辆实车车载 BMS 云端数据（**1,820 万条**有效记录，3 家匿名厂商 DTI/QAS/GIS） | 正常工况 + 稀缺真实安全故障：**热失控、电解液泄漏、内短路、严重老化** | 覆盖最稀缺的真实高危电池故障类与多厂分布边界 |
| **In-service EV Battery Fault Diagnosis (DeFault)** | https://zenodo.org/doi/10.5281/zenodo.19006180 | **CC-BY-4.0** | 同上（DataCite 200） | 在役电动车稀疏电压快照 + 故障标签 + 相空间解耦代码（2026） | 稀疏采样工况下的电芯/电压异常解耦故障码 | 针对车联网稀疏上传场景下的电池故障诊断槽位参考 |
| **Millions-Scale Li-ion Multi-Fault Diagnostics** | https://zenodo.org/doi/10.5281/zenodo.18328700 | **CC-BY-4.0** | 同上（DataCite 200） | 百万级换电/运营电池设备与单体特征 CSV（2026） | `device_level_info.csv`、`cell_level_info.csv`；微短路与低容量多故障溯源 | 补充「电池包（Pack/Device）↔ 单体（Cell）」双层级联故障建模 |
| **Automotive Faults Dataset (Diagnostic & Maintenance)** | https://zenodo.org/doi/10.5281/zenodo.15626055 | **CC-BY-4.0** | 同上（DataCite 200） | `automotive_faults_aktc_obike_et_al.json` + 分系统诊断流程图（2025） | 故障名、症状、分步诊断规程、最终解决方案（涵盖制动/电气/发动机过热/变速箱） | 补足无 DTC 码条件下「症状 → 排查决策树 → 维修结果」结构化实体 |

### 2.4 国内外开放平台与竞赛社区 A 级项（含需登录下载源）

> 注：Kaggle 页面及无鉴权 API 当前受 Google reCAPTCHA 保护（遵循安全边界不作自动化绕过）；国内 AI Studio 等平台下载需免费注册登录。以下基于公开元数据与竞赛规范核实，供使用者凭个人/机构合法账号凭证获取。

| 名称 | 平台与链接 | 许可证 | 获取门槛 | 规模与特点 | 核心字段 | 对本体作用与注意 |
|---|---|---|---|---|---|---|
| **汽车大师问答摘要与推理数据集（原赛题全集）** | 百度 AI Studio（https://aistudio.baidu.com/ 检索「常规赛：汽车大师问答摘要与推理」） | **CC0**（赛题页标注） | 需免费注册百度账号登录下载 | 约 **10.3 万+ 条**（比第一阶段 HF `wushan/vehicle_qa` 1.29 万行大 8 倍） | `QID, Brand, Model, Question, Dialogue, Report` | 补全中文品牌/车型现象与技师多轮问诊报告语料；注意排除 `vehicle_qa` 中已重复的记录 |
| **Vehicle Maintenance Data** | Kaggle（`chavindudulaj/vehicle-maintenance-data`） | **MIT** | 需登录配 `kaggle.json` Token（reCAPTCHA 门禁） | 50,000 行 CSV（**人工合成**） | `Vehicle_Model, Mileage, Maintenance_History, Reported_Issues, Vehicle_Age, Fuel_Type, Battery_Status, Need_Maintenance` | 仅适合作为演示前端/保修提醒预测夹具或对照属性名，**不可当作真实车辆故障分布统计依据** |
| **Vehicle Service and Repair Dataset for Analysis** | Kaggle（https://www.kaggle.com/datasets 搜索对应全称） | **CC0** | 同上 | 售后维修服务历史与常见问题解决表（合成/脱敏汇总） | `CUSTOMER ID, CITY, STATE, SERVICE HISTORY, COMMON PROBLEM, SOLUTION USED, VEHICLE COMPANY` | 补齐客户城市/门店服务历史到常见故障与解决措施的表结构设计 |
| **New Energy Vehicles Diagnosis** | Kaggle（https://www.kaggle.com/datasets 搜索 `New Energy Vehicles Diagnosis`） | **CC0** | 同上 | 新能源电驱系统多传感器诊断数据 | 电压、电流、电机转速、温度、振动、温湿度及电机/逆变器/电池故障类别标签 | 新能源电驱—逆变器故障类别参考 |
| **Electric Vehicle Specs Dataset (2025)** | Kaggle（`urvishahir/Electric-Vehicle-Specs-Dataset-2025`） | **CC-BY-4.0** | 同上 | 470+ 款现代新能源电动车规格表（源自 EV-Database） | 电池容量、续航、快充功率、快充接口类型、整备扭矩、车重尺寸、驱动形式 | 补足 `VehicleModelYear` 对纯电车型三电主数据（电池包容量、快充规格）的缺口 |
| **OBD-II Sensor Anomaly & Failure Prediction** | Kaggle（https://www.kaggle.com/datasets 搜索对应全称） | **MIT** | 同上 | 24 路 OBD-II 传感器时序滑动窗统计特征 + TTF 故障标签 | 发动机转速、车速、节气门、冷却液温、燃油修正、催化器温、模块电压及异常/失效类型 | 适合作为实时遥测异常检测与残余寿命属性对照 |

---

## 3. B 级隔离清单（仅限字段推导与 Schema 参考，严禁入对外 POC 库）

下列数据集虽能直接补齐第一阶段缺失的**国内新能源运行/故障、中文车主投诉分总成、汽车真实维修电子健康档案**等核心视角，但因受**非商用协议、竞赛专用条款、申请审批制或未授权爬取权属限制**，**绝不能打包分发或写入任何对外商业 POC 数据库**，仅保留其字段清单与业务关系供 LinkML 模式设计借鉴：

| 名称 | 平台与链接 | 协议与限制类型 | 实测规模 / 字段形态 | 对本体 Schema 推导的独特贡献 |
|---|---|---|---|---|
| **新能源汽车运行数据（SHEVDC）** | 和鲸社区（https://www.heywhale.com/mw/dataset/605077bcdf26380015a258c2 ） | **`EnableDownload: false`**；明确声明「未经允许不得转载，不得商用」 | 3 份 CSV（2.57 MB，`SHEVDC_OV6N7709(1).csv` 等）；1 台纯电 + 1 台插混，10s 采样 1 天；含 SOC、总电压/电流、温度、里程、PHEV 油电切换 | 唯一可在线直接查看的国内城市级新能源监控数据形状，明确区分纯电与 PHEV 混动模式能耗/电里程槽位 |
| **新能源汽车云端故障诊断模型数据集 / GB/T 32960 运行数据集** | 国家基础学科公共科学数据中心（NBSDC：`https://cstr.cn/16666.11.nbsdc.hXH54nWu`、`https://cstr.cn/16666.11.nbsdc.og8t3c7D`） | 需注册登录并签署《国家基础学科公共科学数据中心数据使用协议》（科研审批与安全限制） | 北京理工大学 / 北理工新源汇交；完全依据 **GB/T 32960 国标** | 提供中国国标 **GB/T 32960 三级报警代码、整车/驱动电机/可充电储能装置极值（最高/最低单体电压及温度探针）、绝缘电阻、DC-DC 状态** 全套标准数据元 |
| **二手车交易价格预测（天池 231784）** | 阿里云天池（https://tianchi.aliyun.com/competition/entrance/231784/introduction ） | 阿里天池竞赛数据协议（仅限参赛与学习，禁止商业分发） | 超 40 万条真实二手车平台脱敏记录 | 提供国内乘用车**上牌时间、品牌/车型编码、里程（`kilometer`）、功率、排量、变速箱、燃油类型与故障损伤标志（`notRepairedDamage`）** 真实分布 |
| **汽车行业用户观点主题及情感识别（CCF BDCI）** | DataFountain（https://www.datafountain.cn/competitions/713 ） | 竞赛专用协议（历史训练赛，禁止赛外二次分发） | 约 1 万条中文汽车用户评价（天池同源「汽车用户情感分析可视化」赛题一致） | 给出中文车主评论的 **10 大结构化主题维度**（动力、价格、内饰、配置、安全性、外观、操控、油耗、空间、舒适性）及情感极性标注模板 |
| **JT/T 1132.3《汽车维修电子健康档案系统 第 3 部分：数据元》与省级规范** | 交通运输部行业标准 / 省级交通厅局电子健康档案平台 | **行业开放标准文档**（真实底层汇总库受交办运〔2021〕82 号限制，仅限车主查单车与持证企业按接口上传，不开放全量下载） | 涵盖全国一/二/三类汽修厂与 4S 店真实完工结算单标准数据元 | **填补国内真实维修工单最大 Schema 空白**：明确标准结构 `维修记录（repair_id, VIN脱敏, 报修描述, 进出厂里程, 结算时间） → 维修项目明细（工时定额/工时费） → 维修配件明细（原厂件号/配件名称/数量）` |
| **国内城市公共充电基础设施开放表** | 北京市公共数据开放平台（`contentID=6d66ce25a94e46429f1379659fde26da`）；深圳市政府数据开放平台（`29200/51500105` 等） | 政务数据开放协议（北京端使用旧版国密/特定 ECC 证书链在部分环境触发 SSL 握手报错；深圳部分数据集需「数据不出域」有条件授权） | 公用充电站运营商、站名、快/慢充接口数、区县与功能区 | 仅在本体日后扩展「充电网络兼容性/补能故障」外部场站维度时作实体参考，离车内诊断较远 |
| **车质网/车主投诉结构形态参考** | 车质网（`12365auto.com`）及 GitHub/和鲸个人爬虫示例（如 `wardxu1985/12365`） | **无官方开源许可**，受平台 `Robots.txt` 及反不正当竞争法约束，**严禁拉取或复用第三方爬虫快照** | 典型字段：`投诉编号、品牌/车系/车型年款、问题类型（质量/服务）、典型故障问题（三级分类）、投诉简述、厂商回复/解决状态` | 仅可作为中文投诉本体分类树（如动力电池衰减、充电跳枪、转向异响、OTA 锁电）的设计参照 |

---

## 4. 双轨连接度实测结论与对 LinkML v3.0 演进的输入

本节全部数字均直接取自本地实测生成的 [extended-probe-stats.json](stats/extended-probe-stats.json)（测量时间：2026-11-25 16:22 Asia/Shanghai）。

### 4.1 轨 1（全球车型与通用诊断轨）：硬键突破与边界暴露

1. **跨国召回硬键实测（Transport Canada VRDB 134,329 行 vs NHTSA 2010+ 248,685 行）**：
   - **全库层**：美加共享 **13,748 个 MMY** 与 **4,131 个完全一致的厂内召回号词元**，成功打通 **4,461 条加拿大召回活动（占加库 27.07%）↔ 4,333 条美国 NHTSA 2010+ 召回活动** 的跨国硬键关联；且加拿大 `SYSTEM_TYPE_ETXT` 到 NHTSA 部件主类的映射率达 **81.23%**。
   - **本田 2018 切片的关键边界揭示**：加拿大库中也包含本田 CR-V / Accord 2018 的 **8 条召回活动（40 行）**，在主题与时间线上与美方高度对应（如 `2018500` 倒车视觉系统、`2020236 / 2023679 / 2024262` 燃油系统、`2023127 / 2026251` 座椅安全带），**但硬键匹配数为 0**！原因在于：加方燃油系统召回未填 `MANUFACTURER_RECALL_NO_TXT`，而倒车与安全带召回中加拿大本田使用了区域独立编码（`HN47`、`HP27`、`AM20`、`HQ40`、`AM96-AN00`），与美方 NHTSA 填报的 `K2G/V2F`、`X95`、`BDC/MDD`、`KGC/KGD` **并不共用同一套厂内代码**。这证明跨国多司法管辖区召回建模时，不能把单国 `MFGCAMPNO` 假设为全球通用主键。
2. **英国 DVSA MOT 检查层级对齐（`lookup.zip` 实测）**：
   - Class 4 乘用车目录包含 **934 个部件节点（最大 5 层）** 与 **4,432 条法定拒检缺陷（RFR）**，明确区分 `Major`（1,196）、`Dangerous`（525）、`Minor`（200）及 `Pre-EU Directive`（2,511），配合 **129 个三维安装方位**，弥补了 NHTSA 只写部件路径却无「损坏严重度」与「里程分布」的缺口。
   - 将 MOT 30 个顶层大类映射到 NHTSA 部件主类，覆盖率达 **83.33%（25/30）**。
3. **开源 DTC 码表扩展与「同码多厂多义」发现**：
   - 合并 `CodesList`（9,414）+ `Wal33D`（12,128 唯一码 / 33 厂商）+ `OBDex`（9,533 审校码 + 132 PIDs），合规开源码池扩大至 **12,412 个唯一码（净增 +2,998 码，+31.85%）**。
   - 对照第一阶段 [join-stats.json](stats/join-stats.json) 中从 NHTSA 投诉叙述抽出的 **Top 20 高频码**：基线 `CodesList` 命中 17/20，加入 `Wal33D` 后提升至 **18/20**，成功覆盖此前高居第 1 位的缺失厂标码 **`P1326`**（580 行）。
   - **重要模型修正**：实测发现 `Wal33D` 中 `P1326` 仅录入了 `VOLKSWAGEN` 定义，而在 NHTSA 投诉高发场景中 `P1326` 大量对应现代/起亚爆震传感器检测系统（KSDS），另外底盘厂标码 `C1391`（359 行）与 `C2200`（191 行）仍未被三库覆盖。因此，下一版 LinkML 模型必须将厂标 `DTC` 释义建模为 **`(dtc_code, make)` 上下文关联节点**，绝不能用单一 `code` 字符串直接覆盖所有品牌！
4. **VSS v6.1 与 `opendbc` 车端总线桥接**：
   - 实测发现 **COVESA VSS v6.1 已移除早期独立的 `Vehicle.OBD` 树**，仅保留 `Vehicle.Diagnostics.DTCCount` 与 `Vehicle.Diagnostics.DTCList`（2 个诊断叶子）；实况 OBD PID 定义恰好可由 **OBDex `mode01/mode09`（132 个带公式和量程的 PID）** 无缝补足，历史语义类可参考 **W3C VSSo `vss_rel_2.2.ttl`（508 类）**。
   - 本田与新能源实车 `opendbc`（如 `_bosch_2018.dbc` 166 信号、`_honda_common.dbc` 160 信号、`byd_atto3.dbc` 103 信号、`tesla_powertrain.dbc` 74 信号）可将具体 `BO_/SG_` 报文（如 `HYBRID_BRAKE_ERROR`、`ACC_CONTROL`、`STEERING_CONTROL`）挂载到 NHTSA 的 `FORWARD COLLISION AVOIDANCE`、`SERVICE BRAKES` 与 `STEERING` 节点。

### 4.2 轨 2（新能源三电与中文专项轨）：新增能力与槽位建议

面向无美规本田交集的新能源三电、中文售后及完整诊断决策链，本轮调研已实证以下 4 组可直接写入 LinkML v3.0 候选扩展模块的槽位群（不修改当前 v1 试验模型，待后续决策启用）：

| 扩展候选模块 | 实证来源 | 建议新增类 / 槽位（仅作数据推导依据） |
|---|---|---|
| **新能源动力电池与三电观测** | Figshare `23301881` / `23659323` / `30162841`、Zenodo `10656500` / `19006180` / `18328700`、VSS v6.1 `TractionBattery.*`（96 项）& `ElectricMotor.*`（84 项）、GB/T 32960（B 级） | `TractionBatteryObservation`：`cellVoltageMin/Max`、`cellTemperature`、`stateOfCharge`、`stateOfHealth`、`insulationResistance`、`chargingSessionPhase`、`thermalRunawayFlag`、`microShortCircuitFlag` |
| **定期年检与实车里程缺陷史** | 英国 DVSA MOT (`lookup.zip` + 年度大包) | `PeriodicInspectionRecord`：`testMileage`、`firstUseYear`、`fuelTypeCode`、`motTestOutcome`、`rfrItemGroup`、`rfrLocation`、`defectSeverity` |
| **多司法管辖区召回与厂内编码** | 加拿大 VRDB + 美国 NHTSA + 欧盟 Safety Gate | `JurisdictionRecall`：`jurisdiction`、`officialRecallId`、`manufacturerRecallNumber`、`recallCategory`、`unitsAffected` |
| **无码症状—诊断流程—修复闭环** | Zenodo `15626055` + JT/T 1132.3 数据元（B 级）+ 百度汽车大师（CC0） | `DiagnosticFlowchart` / `WorkOrderLine`：`symptomList`、`diagnosticProcedureSteps`、`resolutionOutcome`、`laborHours`、`oemPartNumber` |

---

## 5. 排除与避坑清单及终极缺口坦白

### 5.1 本轮核查后明确排除的数据源

| 排除对象 | 来源平台 | 实测真相与排除原因 |
|---|---|---|
| **“Warranty Claims Dataset (`df_Clean.csv`)”** | Kaggle / GitHub（`SUKHMAN-SINGH-1612/Data-Science-Projects` 等） | **重大跨行业误标陷阱**：拉取样本表头核实为 `Product_category=Household/Entertainment`, `Product_type=AC/TV`, `AC_1001_Issue`, `TV_2001_Issue`——系空调与电视家电保修欺诈集，**与汽车毫无关系**。 |
| **Figshare ID `23293883`** | Figshare（部分检索摘要误引为 EVBattery） | API 实测为医学肠道菌群论文附表 `Table_4_Alterations_of_the_gut_microbiota...docx`，**真正 *EVBattery* 编号为 `23301881`**。 |
| **`mytrile/obd-trouble-codes`** | GitHub | 实测根目录无 `LICENSE` 文件，且 README 写明抓取自 `obd-codes.com`，许可不明，不得替代 `OBDex` / `Wal33D`。 |
| **`Automotive-9/dtc-codes` / `MCDxAI/open-source-dtc-databases`** | GitHub / GitLab | `MCDxAI` 无 `LICENSE`（404）且链接超时；`Automotive-9` 已迁移 GitLab `GhostTypes/dtc-codes` 且同样缺乏清晰 SPDX 开源许可文件，虽然宣称含 31,272 条厂标码，因权属不清暂不列入 A 级可用。 |
| **`Leo-Thomas/EngineFaultDB`** | GitHub | 55,999 行实验室 C14NE 发动机故障数据真实存在，但采用 **GPL-3.0** 强传染性协议，与本仓库 `Apache-2.0` 及商用 POC 兼容存在风险，若使用须严格物理隔离。 |
| **`awslabs/aws-fleet-predictive-maintenance`** | GitHub | 仅含 230 字节 `README.md` 预览占位符，无实际公开数据文件，属于空壳仓库。 |
| **OpenDataLab 汽车类集（`CompCars`、`BDD100K` 等）** | OpenDataLab | 全部为车辆外观图像边界框、车道线与自动驾驶多视角感知数据集，与售后故障诊断/知识库本体无关，按本轮范围边界排除。 |

### 5.2 公开数据依然盖不住的终极缺口（仍须等主机厂脱敏样本）

即便跨平台拓展到四大阵地并核实了 20+ 个高质量新源，以下核心售后数据**在全球公开互联网上依然不存在可商用的结构化替代品**，必须依赖后续项目甲方/主机厂提供脱敏业务样本：
1. **真实汽车主机厂 8D 报告与根因闭环记录**（FMEA 失效模式 ↔ 工程变更 ↔ 索赔核销关闭）；
2. **真实保修索赔工单与 4S 店工时/备件结算流水**（JT/T 1132.3 给出了国家标准字段定义，Kaggle 仅存合成样例，真实带 OEM 零件号、故障工位代码与索赔拒赔原因的工单全行业不公开）；
3. **特定车型原厂维修手册（Shop Manual）、电路图（Wiring Diagram）与 TSB 维修全文解析集**；
4. **车联网 App 用户反馈（远程控车、数字钥匙、智驾 OTA 体验吐槽）及脱敏后的中国本土车企专属诊断代码（UDS DID/Routine/DTC 扩展库）**。

核查截止：2026-11-25 Asia/Shanghai。所有统计均在本地落盘执行并通过隐私脱敏校验，未对存在反爬/CAPTCHA 拦截的站点执行自动化绕过。
