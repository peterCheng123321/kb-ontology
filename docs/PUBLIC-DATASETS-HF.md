# 公开数据集核查（Hugging Face + 官方源）

- 日期：2026-11-24（Asia/Shanghai）
- 目的：POC 本体 v3.0 已去掉能力预设，能力和字段要从数据推导；在尚无授权的主机厂样本时，先用可核实的公开数据顶上。
- 方法：Hugging Face Hub API（`/api/datasets?search=...&full=true`）中英关键词检索，再核对 dataset card / README、仓库文件列表、datasets-server 的 info / 预览（只看字段名、行数、语言痕迹，不下载大文件进仓库，不在文档中写出 VIN 或个人标识取值）。官方源核对 NHTSA 目录页、data.gov、`static.nhtsa.gov` 字段字典与文件 HEAD，以及市场监管总局召回信息公开页。
- 检索范围：车辆诊断 / OBD-II / DTC（含 PID）、维修保修与售后记录、召回与投诉、手册与技术文档 QA、车载日志 / CAN / 遥测、车联网 App 反馈、8D / 质量问题、中文汽车语料（汽车之家、车主投诉等）。关键词覆盖 automotive、vehicle、car repair、OBD、DTC、CAN bus、warranty、recall、NHTSA、汽车、故障、维修、车主 等。
- 不做的事：不把大语料写入任何 git 仓库，不把密钥或未公开业务数据写入仓库。中文关键词在 HF datasets API 上命中为 0；中文相关集合是在英文名（尤其 BAAI IndustryCorpus / IndustryInstruction、wushan/vehicle_qa、微博汽车子集）下找到的。
- 许可证口径：美国政府作品（NHTSA 源文件）按公有领域 / Public Domain U.S. Government 理解，可作商用与 POC，但仍须遵守隐私与“不得暗示官方背书”的限制。`cc-by-4.0` / `apache-2.0` / `MIT` 一般可用于 POC 与商用（需署名或保留声明）。`cc-by-nc-4.0` 与明确“仅评估、禁止商用”的 `other` 许可证不能当作可商用数据。`ODbL` 可用于 POC，但再分发派生数据库有 share-alike 义务。许可证为空或 README 404 的，不视为可自由使用。

---


## 0. 直接下载链接（2026-11-24 核对）

下列地址为完整 URL。`static.nhtsa.gov` 与 Hugging Face 数据集页已核对返回 HTTP 200。官方门户 https://www.nhtsa.gov/nhtsa-datasets-and-apis 是 NHTSA 数据集说明页；部分网络环境对该门户会返回 403，但不影响直接文件链接。第三方原始文件请下载到本地，不要提交到本仓库。

### NHTSA（公有领域）

- 官方说明：https://www.nhtsa.gov/nhtsa-datasets-and-apis
- 投诉平面文件：https://static.nhtsa.gov/odi/ffdd/cmpl/FLAT_CMPL.zip
- 投诉字段字典：https://static.nhtsa.gov/odi/ffdd/cmpl/CMPL.txt
- 2010 年后召回：https://static.nhtsa.gov/odi/ffdd/rcl/FLAT_RCL_POST_2010.zip
- 2010 年前召回：https://static.nhtsa.gov/odi/ffdd/rcl/FLAT_RCL_PRE_2010.zip
- 召回字段字典：https://static.nhtsa.gov/odi/ffdd/rcl/RCL.txt
- 缺陷调查：https://static.nhtsa.gov/odi/ffdd/inv/FLAT_INV.zip
- 调查字段字典：https://static.nhtsa.gov/odi/ffdd/inv/INV.txt

厂商通信 / TSB 平面文件的官方前缀是 `https://static.nhtsa.gov/odi/ffdd/tsbs/`。该目录本身不提供文件列表，请用下面已核对可下载的直接链接：

- 字段字典：https://static.nhtsa.gov/odi/ffdd/tsbs/TSBS.txt
- https://static.nhtsa.gov/odi/ffdd/tsbs/TSBS_RECEIVED_2015-2019.zip
- https://static.nhtsa.gov/odi/ffdd/tsbs/TSBS_RECEIVED_2020-2024.zip
- https://static.nhtsa.gov/odi/ffdd/tsbs/TSBS_RECEIVED_2025-2026.zip
- https://static.nhtsa.gov/odi/ffdd/tsbs/MFR_COMMS_RECEIVED_2015-2019.zip
- https://static.nhtsa.gov/odi/ffdd/tsbs/MFR_COMMS_RECEIVED_2020-2024.zip
- https://static.nhtsa.gov/odi/ffdd/tsbs/MFR_COMMS_RECEIVED_2025-2026.zip

许可证：美国政府作品，公有领域。用途：投诉、召回、调查、厂商通信的结构化字段，以及召回原厂零件号；用来推导售后关系并做本田 2018 试验。

### Hugging Face 数据集

- https://huggingface.co/datasets/wushan/vehicle_qa — 许可证 Apache-2.0。用途：中文故障问诊与诊断对话，按品牌、车型、部件词表做弱关联。
- https://huggingface.co/datasets/CodesList/obd2-codes — 许可证 CC BY 4.0（需署名）。用途：OBD-II / DTC 词表。第三方汇编，不是 SAE J2012 官方文本。
- https://huggingface.co/datasets/Ichlibitiche/mechanicdb-obd2-repair-sample — 许可证 ODbL 1.0（署名 + 相同方式共享）。用途：故障码到维修步骤、零件、工时的样本关系。完整库另行收费。
- https://huggingface.co/datasets/BAAI/IndustryInstruction_Automobiles — 许可证 Apache-2.0。用途：中英汽车领域指令问答，辅助能力用语或作为检索语料，不是结构化工单。
- https://huggingface.co/datasets/BAAI/IndustryCorpus_automobile — 许可证 Apache-2.0。用途：汽车领域网页语料，适合作为检索文档，不宜单独推导字段。
- https://huggingface.co/datasets/BAAI/IndustryCorpus2_automobile — 许可证 Apache-2.0。用途：同上，后续版本语料。
- https://huggingface.co/datasets/PedroCuisinier2025/OBD2_panel_opel_2012 — 许可证以数据集卡片为准。用途：真实 OBD-II PID / 遥测字段形状，不是投诉或召回。


## 1. 前 5 推荐与理由

按「能否支撑从数据推导能力/字段、许可是否允许 POC、是否真实可访问、与售后知识库本体的贴合度」排序。第 1 项为官方源（非 HF），其余 4 项为已核实的 HF 数据集。

| 序 | 名称 | 位置 | 许可证 | 规模（已核实） | 一句用途 |
|---|---|---|---|---|---|
| 1 | NHTSA ODI 投诉、召回、缺陷调查平面文件 | 非 HF： [NHTSA Datasets and APIs](https://www.nhtsa.gov/nhtsa-datasets-and-apis)；下载 [FLAT_CMPL.zip](https://static.nhtsa.gov/odi/ffdd/cmpl/FLAT_CMPL.zip)、[FLAT_RCL_POST_2010.zip](https://static.nhtsa.gov/odi/ffdd/rcl/FLAT_RCL_POST_2010.zip) / [FLAT_RCL_PRE_2010.zip](https://static.nhtsa.gov/odi/ffdd/rcl/FLAT_RCL_PRE_2010.zip)、[FLAT_INV.zip](https://static.nhtsa.gov/odi/ffdd/inv/FLAT_INV.zip)；字段字典 [CMPL.txt](https://static.nhtsa.gov/odi/ffdd/cmpl/CMPL.txt)、[RCL.txt](https://static.nhtsa.gov/odi/ffdd/rcl/RCL.txt)、[INV.txt](https://static.nhtsa.gov/odi/ffdd/inv/INV.txt)；data.gov 投诉条目亦标注 `us-pd` | 美国政府作品，公有领域（Public Domain U.S. Government） | 投诉文件每日更新；目录页记 FLAT_CMPL.zip 约 360 MB（更新 2026-11-23 05:08 ET，合 18:08 中国时区）。官方未公布实时行数。2026-10-10 第三方完整抓取记录投诉平面文件 2,255,013 行（投诉-部件行，需按 `ODINO` 去重）；召回预/后 2010 两个包合计约 32.7 万行量级；调查文件同日可访问（HEAD 200，Last-Modified 2026-11-23 09:03:53 GMT，合 17:03 中国时区） | **优先用来推导投诉/工单类字段**（部件、故障叙述、里程、事故/起火、召回缺陷与纠正措施、调查主题） |
| 2 | [wushan/vehicle_qa](https://huggingface.co/datasets/wushan/vehicle_qa) | HF，hub 200，非 gated，预览可用 | Apache-2.0 | datasets-server：训练 12,038 + 全表约 12,943 行；字段 `QID, Brand, Model, Question, Dialogue, Report`；抽检为中文 | **中文故障问诊/诊断对话**，用来推导现象、对话轮次与诊断结论字段 |
| 3 | [CodesList/obd2-codes](https://huggingface.co/datasets/CodesList/obd2-codes) | HF，hub 200，非 gated，预览可用 | CC-BY-4.0（卡片写明可商用，需署名） | 9,414 条；约 1.08 MB；字段 `code, description, category, severity` | **DTC 词表**：推导故障码、描述、类别、严重度 |
| 4 | [Ichlibitiche/mechanicdb-obd2-repair-sample](https://huggingface.co/datasets/Ichlibitiche/mechanicdb-obd2-repair-sample) | HF，hub 200，非 gated，预览可用 | ODbL v1.0（署名 + share-alike）；完整库另行收费 | 免费样本约 90 个码（75 个 SAE 通用 + 15 个厂标），多表合计约 1,191 行 / 0.27 MB；表含 `dtc_codes`、`diagnostic_fixes`、`dtc_fixes_joined`、`replacement_parts` | **故障码 → 处理步骤 / 零件 / 工时** 的关系字段，样本即可看清表结构 |
| 5 | [BAAI/IndustryInstruction_Automobiles](https://huggingface.co/datasets/BAAI/IndustryInstruction_Automobiles) | HF，hub 200，非 gated，预览可用 | Apache-2.0 | 126,707 条中英 instruction 对话；约 98 MB（server 统计）；字段 `id, lang, conversations, deita_score, rw_score, length` 等 | **中英汽车领域用户问题与问答**，辅助看能力该怎么命名；并可作为 RAG / 指令语料。配套网页语料见下文 IndustryCorpus，只适合当文档 |

理由摘要：

1. HF 上几乎所有 NHTSA 集合都是 1,000 行样品、空仓库或付费打包；要做字段推导应直接用官方日更平面文件。投诉叙述对应故障现象，`COMPDESC` 对应部件，召回的缺陷 / 后果 / 纠正措施对应处理方案，调查表可把投诉与召回串起来。这是目前最接近「售后工单 + 质量投诉」的公开结构数据。注意字段 15 `VIN`（11 位）、城市州、经销商电话、车辆操作人姓名等个人或准标识信息：**本体示例与对外文档只写字段名，不写取值**。投诉是车主陈述，不是已证实的缺陷。
2. 中文关键词在 Hub 上没有汽车之家或车主投诉专集。`vehicle_qa` 是目前核实到的、许可清晰、带品牌/车型/问题/多轮对话/报告的中文结构化集，最适合补中文现象与问诊能力。卡片几乎无溯源，疑似竞赛或「汽车大师」类数据转载，使用前应再做一轮版权与去重检查。
3. 需要一份可商用的通用 DTC 词表。该集规模明显大于只有几十条的无许可证仓库，字段干净。它是第三方汇编（obdcodeslist.com），**不是 SAE J2012 官方文本**，不能当法规引用源。
4. 词表不够，还要「码到怎么修」。MechanicDB 样本把 DTC、步骤、难度、零件、工时拆成多表，正好用来设计对象关系。完整版是付费产品；ODbL 若对外发布派生库有 share-alike。
5. 中文售后场景还需要「用户会问什么」的语言证据。IndustryInstruction 汽车子集许可友好、中英都有、体量足够。它不是工单，不能单独推导结构化字段，但可以支撑能力表述和 RAG。更大体量的网页抓取见 IndustryCorpus / Corpus2。

---

## 2. 哪些能推导能力/字段，哪些只适合当 RAG 文档

### 适合推导能力与字段（结构化或准结构化）

- **官方 NHTSA 投诉 / 召回 / 调查**（非 HF）：工单/投诉、故障现象（`CDESCR`）、部件（`COMPDESC` / `COMPNAME`）、车辆主体（make/model/year，注意不要把 VIN 做成可检索标识）、处理方案（召回 `CORRECTIVE_ACTION` 及缺陷/后果摘要）、调查过程字段。
- **wushan/vehicle_qa**：中文问诊对话、诊断报告、品牌车型。
- **CodesList/obd2-codes**、**mechanicdb-obd2-repair-sample**、（次选）**fabiovilao/obd2-ptbr**：DTC 与维修方案字段。
- **PedroCuisinier2025/OBD2_panel_opel_2012**：真实 PID / 遥测字段（转速、车速、水温、燃油修正、负荷等），用于冻结帧 / 实况数据槽位，不是工单。
- **vic35get/nhtsa_complaints_dataset**、**iqbaltaher/us-vehicle-owner-complaints-by-model-2010-2025**：部件分类或按车型汇总，可补「部件体系 / 投诉计数」，叙事完整性不如官方源。
- **Growing-Moss-Data/automotive-service-intelligence-sample**：售后发票、服务历史、车辆与门店关系的字段形状很有参考价值，但许可证明确禁止商用与再分发，**只可在评估许可范围内看 schema，不能当作 POC 训练或产品数据**。
- **williamTLmiller/nhtsa-vehicle-recalls-complaints-defects**：链接后的失败模式 / 根因 / 纠正措施字段最丰富，但是 **CC-BY-NC-4.0 玩具样本**，且部分标签为作者预测，不是 NHTSA 原字段。商用不可直接用；看字段形状可以，采用其预测标签需谨慎。

### 只适合当 RAG 文档或开放域问答（不宜当工单 schema 来源）

- **BAAI/IndustryCorpus_automobile**、**BAAI/IndustryCorpus2_automobile**：中英汽车领域网页/语料抓取，体量大、噪声也大。
- **BAAI/IndustryInstruction_Automobiles**：指令问答，可辅助能力用语，不是工单。
- **aowens25/NHTSA**：约 21.6 万条召回相关文档摘要（`DOCUMENT NAME` 形如厂商召回 PDF 文件名 + `SUMMARY`），可作召回沟通/技术通告类检索语料；汇编许可证为 Apache-2.0，但原文可能仍受厂商版权约束，只适合检索摘要，不要当可再发布全文。
- **DealerMax** 意大利语 FAQ / 指南 / 术语表：经销商面向消费者的知识文档，市场与语言不对齐，最多当 RAG 样例。
- **m4rque2/weibo_automobile**：100 万条微博文本，噪声高，最多观察车主语言，不能当结构化投诉。
- **zhengr/Automotive_Industry_Fault_Data_Set**：中文「故障」指令抽取，模板单一；20 条抽检里同时出现汽车和更泛的故障表述，不宜单独当车企工单源。
- **Muhammmadd/iso26262-automotive-safety-requirements**、**ron164/automotive_requirements**、**pjaekae/automotive_engineering**：功能安全 / 需求，不是售后工单。
- **jinaai/automobile_catalogue_jp**：车型目录，离售后诊断较远。

### 目前公开数据盖不住、仍要等脱敏样本的块

- 车企内部 8D / 保修工单 / 技师工时明细（Growing-Moss 只有不可商用的样品结构）。
- 汽车之家问答、中国车主投诉平台的可再分发语料（HF 上未找到可核实专集）。
- 车联网 App（寻车/定位等）用户反馈专集。
- 原始 CAN 总线日志（核实到的是 OBD-II PID 遥测，不是原始 CAN）。
- 与具体车型绑定的官方维修手册 / 电路图 QA（HF 上无许可清晰的 OEM 手册全集）。

---

## 3. 按适配度排序的已核实清单（HF）

下列均已用 Hub API 打开（HTTP 200）。未核实、404、或仓库无数据的不进入「可用」推荐。

### 3.1 投诉 / 召回 / 调查（HF 镜像，完整数据请回官方源）

| 名称 | 链接 | 许可证 | 规模 | 语言 | 关键字段 | 对本体 | 质量与注意 |
|---|---|---|---|---|---|---|---|
| aowens25/NHTSA | https://huggingface.co/datasets/aowens25/NHTSA | Apache-2.0 | 216,141 行，约 69 MB（server） | 英 | `NHTSA ID, DOCUMENT NAME, MAKE, MODEL, MODEL YEAR, SUMMARY` | 召回沟通摘要，偏知识文档 | README 几乎为空；前 100 行文档名均为召回相关 PDF；适合 RAG，不宜替代官方平面文件 |
| vic35get/nhtsa_complaints_dataset | https://huggingface.co/datasets/vic35get/nhtsa_complaints_dataset | Apache-2.0 | 12,534 行（train/eval/test），约 6.4 MB | 英（卡片葡萄牙语说明） | `odiNumber, dateComplaintFiled, components, summary, label` | 投诉叙述 + 部件分类 | 2014–2024 子集，标签合并为电气/气囊/结构/制动/其他，不是全量 |
| iqbaltaher/us-vehicle-owner-complaints-by-model-2010-2025 | https://huggingface.co/datasets/iqbaltaher/us-vehicle-owner-complaints-by-model-2010-2025 | CC-BY-4.0；底层为 NHTSA 政府数据 | 90,254 行，约 6.5 MB | 英 | `make, model, model_year, component, complaints, year_total` | 按车型-部件的投诉计数 | 汇总表，无叙述；覆盖 2010–2025 年款、卡片称 4,087 个车型组合 |
| williamTLmiller/nhtsa-vehicle-recalls-complaints-defects | https://huggingface.co/datasets/williamTLmiller/nhtsa-vehicle-recalls-complaints-defects | **CC-BY-NC-4.0**（作者规范化与预测标签；底层 NHTSA 记录本身仍是政府数据，可回官方源另取） | 玩具样本，多表合计约 15,459 行 / 3.8 MB；完整版为付费产品 | 英 | 投诉/召回/调查/厂商沟通及 `failure_modes, root_causes, corrective_actions, component_*` 等 | 字段形状参考价值高 | **不可商用**；部分链接与标签为作者预测，不是 NHTSA 原值 |
| claritystorm/nhtsa-vehicle-complaints | https://huggingface.co/datasets/claritystorm/nhtsa-vehicle-complaints | `other` / 卡片 `license_name: public-domain`；**HF 上只有 1,000 行样品**，完整包卡片标价 $79 | 样品 1,000 行；卡片称完整快照 2,189,824 部件行 / 1,582,110 个 `odino`（至 2026-03） | 英 | 与官方接近：`cmplid, odino, mfr_name, make, model, model_year, comp_desc, complaint_desc, miles` 等 | 同官方投诉 | 直接用官方免费文件，不必买快照。卡片亦提醒失败日期/年款有异常值 |
| claritystorm/nhtsa-vehicle-recalls | https://huggingface.co/datasets/claritystorm/nhtsa-vehicle-recalls | 同上；完整包卡片标价 $59 | 样品 1,000 行；卡片称完整 176,073 产品行 / 29,865 个活动号（至 2026-03） | 英 | `campno, maketxt, modeltxt, compname, desc_defect, conequence_defect` 等 | 同官方召回 | 同上，回官方源 |
| earino/factory-nhtsa-pe-recall | https://huggingface.co/datasets/earino/factory-nhtsa-pe-recall | `other`：上游 Public Domain U.S. Government；汇编附加权利 CC0-1.0，代码 MIT | 1,153 行 | 英 | `investigation_id, make, model, model_year, component, manufacturer, vehicle_age, open_date, recall_24m` | 调查是否在 24 个月内导致召回的预测任务 | 衍生实验集，不是通用工单表 |
| ItsMayur/Vehicle_Complaints_NHSTA | https://huggingface.co/datasets/ItsMayur/Vehicle_Complaints_NHSTA | MIT | 1,063 行 | 英 | 投诉类字段（NHTSA 派生） | 小样本投诉 | 拼写为 NHSTA；体量小，优先官方或 vic35get |
| ProblemsByVin/nhtsa-investigations | https://huggingface.co/datasets/ProblemsByVin/nhtsa-investigations | CC-BY-4.0 | 585 行 | 英 | 调查相关 | 调查摘要小样本 | 完整调查请用官方 FLAT_INV |
| alea-institute/kl3m-data-dotgov-www.nhtsa.gov | https://huggingface.co/datasets/alea-institute/kl3m-data-dotgov-www.nhtsa.gov | CC-BY-4.0 | 474 行，约 5.3 MB | 英 | 政府站点抓取文本 | 仅 RAG | 不是结构化投诉表 |
| tensorust/nhtsa-complaint-spikes-sample | https://huggingface.co/datasets/tensorust/nhtsa-complaint-spikes-sample | other | 48 行 | 英 | 投诉峰值样例 | 过小 | 仅演示 |
| redflags33/nhtsa | https://huggingface.co/datasets/redflags33/nhtsa | **许可证空，无 README** | 500 行，预览可用 | 英 | — | 不推荐作为依据 | 存在但许可不明 |
| claritystorm/nhtsa-fars-1975-2023 | https://huggingface.co/datasets/claritystorm/nhtsa-fars-1975-2023 | other / public-domain 口径；HF 仅 1,000 行样品 | 样品 1,000 | 英 | 致命事故 FARS | 碰撞统计，离售后工单远 | 如需 FARS 应走 NHTSA 官方 FARS，而不是售后本体优先集 |

### 3.2 诊断 / OBD-II / DTC

| 名称 | 链接 | 许可证 | 规模 | 语言 | 关键字段 | 对本体 | 质量与注意 |
|---|---|---|---|---|---|---|---|
| CodesList/obd2-codes | https://huggingface.co/datasets/CodesList/obd2-codes | CC-BY-4.0 | 9,414 行，约 1.08 MB | 英 | `code, description, category, severity` | DTC 词表 | 第三方汇编，非 SAE 官方 |
| Ichlibitiche/mechanicdb-obd2-repair-sample | https://huggingface.co/datasets/Ichlibitiche/mechanicdb-obd2-repair-sample | ODbL v1.0 | ~1,191 行 / 90 个码的免费样本 | 英 | `dtc_code, short_description, detailed_technical_explanation, fix_title, step_by_step_instructions, difficulty_level, est_labor_hours, part_name` 等 | DTC + 处理方案 + 零件 | 完整版收费（卡片标 $49 / $149）；码定义称源自 MIT 许可的 J2012 派生整理 |
| PedroCuisinier2025/OBD2_panel_opel_2012 | https://huggingface.co/datasets/PedroCuisinier2025/OBD2_panel_opel_2012 | CC-BY-4.0 | 394,406 行，约 107 MB | 传感数值，文档英 | `timestamp, RPM, SPEED, THROTTLE_POS, MAF, COOLANT_TEMP, ENGINE_LOAD` 等 28 列 | PID / 冻结帧槽位 | 单车（2012 Opel Corsa）真实 ELM327 采集，2025-04-30 至 2025-12-02；含派生油耗/扭矩字段 |
| fabiovilao/obd2-ptbr | https://huggingface.co/datasets/fabiovilao/obd2-ptbr | CC-BY-4.0 | 2,973 行，约 1.6 MB | 葡语描述为主 | `Code, Description, cdescr` | DTC 词表（非中英） | 可作多语言对照，不是中文优先 |
| RRK1987/automotive-dtc-finetune | https://huggingface.co/datasets/RRK1987/automotive-dtc-finetune | MIT | 140 条（119/21） | 英 | `system, user, assistant, dtc_code, dtc_system, severity, category, vehicle, is_safety_critical` | 诊断问答微调 | 规模很小，可能含生成文本，只宜对照字段 |
| Epitech/obd-codes-fine-tune | https://huggingface.co/datasets/Epitech/obd-codes-fine-tune | **许可证空** | 3,071 行 | 英 | `instruction, input, output`（抽检 input 常为空） | 微调语料 | 无许可证，不建议纳入产品 |
| CJJones/Vehicle_Diagnostics_LLM_Training_Sample 与 Janukshan/ 同名集 | https://huggingface.co/datasets/CJJones/Vehicle_Diagnostics_LLM_Training_Sample ；https://huggingface.co/datasets/Janukshan/Vehicle_Diagnostics_LLM_Training_Sample | **CC-BY-NC-4.0** | 各 32,732 行，体积相同（约 1.21 MB） | 英 | `text` | 诊断叙述样本 | **不可商用**；两库规模一致，疑似复制。卡片提到付费次数后或改许可，以当前卡片为准 |
| jigneshk5/dtc_codes | https://huggingface.co/datasets/jigneshk5/dtc_codes | **无许可证、README 404** | 预览 40 行；另有 `dtc_codes_full.jsonl` | — | `code, cause, severity, suggested_fix` | 字段可看，不能当合法数据源 | 不推荐使用 |
| Febachetti/automotive-error-codes | https://huggingface.co/datasets/Febachetti/automotive-error-codes | **无许可证、README 404** | 10 行 | 葡/西一类 | `Codigo, Descricao, Marca` | 过小 | 不推荐 |

### 3.3 中文与多语言汽车语料 / 手册 QA

| 名称 | 链接 | 许可证 | 规模 | 语言 | 关键字段 | 对本体 | 质量与注意 |
|---|---|---|---|---|---|---|---|
| wushan/vehicle_qa | https://huggingface.co/datasets/wushan/vehicle_qa | Apache-2.0 | ~12,943 行（train 12,038） | 中文（抽检 Question/Dialogue/Report 含大量汉字） | `QID, Brand, Model, Question, Dialogue, Report` | 现象、问诊、诊断报告 | README 仅许可证；溯源薄 |
| BAAI/IndustryInstruction_Automobiles | https://huggingface.co/datasets/BAAI/IndustryInstruction_Automobiles | Apache-2.0 | 126,707 条，约 98 MB | 中、英 | `conversations, lang, deita_score, rw_score` | 能力用语 + RAG/指令 | 构造细节见父集 IndustryInstruction；`instruction` 字段抽检常空，正文在 conversations |
| BAAI/IndustryCorpus_automobile | https://huggingface.co/datasets/BAAI/IndustryCorpus_automobile | Apache-2.0 | datasets-server 登记 993,778 条；Hub 文件约 19.2 GB（中文约 10.7 GB，英文约 8.5 GB） | 中、英 | `id, text, industry_type` | 仅 RAG / 预训练 | 来自开放语料清洗（WuDao、CCI、RedPajama、SkyPile 等），有重复与噪声；勿整包塞进 git |
| BAAI/IndustryCorpus2_automobile | https://huggingface.co/datasets/BAAI/IndustryCorpus2_automobile | Apache-2.0 | Hub 文件约 23.6 GB（中文 high/middle/low 约 0.90+9.66+2.97 GB，英文约 1.37+7.06+1.63 GB）；datasets-server 未给出总行数 | 中、英 | 按质量分层的 parquet | 仅 RAG / 预训练 | 父集 IndustryCorpus2 的汽车子集；体量大，不要下进仓库 |
| m4rque2/weibo_automobile | https://huggingface.co/datasets/m4rque2/weibo_automobile | MIT | 1,000,000 行，server 约 181 MB / 下载约 117 MB | 中文 | `id, text, url` | 车主口语观察 | 社交媒体噪声、广告、转发多；可能含个人表达，使用需过滤 |
| zhengr/Automotive_Industry_Fault_Data_Set | https://huggingface.co/datasets/zhengr/Automotive_Industry_Fault_Data_Set | Apache-2.0 | 1,441 行 | 中文 | `instruction, input, output` | 故障信息抽取样例 | README 几乎为空；20 条抽检共用同一 instruction 模板，主题混有汽车与更泛的「故障」 |
| DealerMax/italian-automotive-faq | https://huggingface.co/datasets/DealerMax/italian-automotive-faq | CC-BY-4.0 | 139 条 | 意大利文 | `question, answer, category` | RAG 样例（购车/金融/售后 FAQ） | 语言与市场不对齐 |
| DealerMax/italian-automotive-guides | https://huggingface.co/datasets/DealerMax/italian-automotive-guides | CC-BY-4.0 | 22 篇长文 | 意大利文 | `h1, body_html, topic` | RAG | 同上 |
| DealerMax/italian-automotive-glossary | https://huggingface.co/datasets/DealerMax/italian-automotive-glossary | CC-BY-4.0 | 212 条 | 意大利文 | `term, definition, category` | 术语表样例 | 同上 |

### 3.4 售后服务记录、遥测、其它相关但适配度较低

| 名称 | 链接 | 许可证 | 规模 | 语言 | 关键字段 | 对本体 | 质量与注意 |
|---|---|---|---|---|---|---|---|
| Growing-Moss-Data/automotive-service-intelligence-sample | https://huggingface.co/datasets/Growing-Moss-Data/automotive-service-intelligence-sample | **other：商业样品许可，仅研究/评估/内部测试，禁止商用、再分发、公开训练模型** | 样品：客户/车辆各 100、发票 1,029、服务行 4,417、门店 69（导出说明 2026-06-28）；server 合计约 5,949 行 | 英 | 发票、服务历史、车辆、门店、业务类型（含预防性保养 / 维修等） | 售后工单 schema 参考 | 标识已哈希；完整库为商业产品（卡片称源库千万级车辆/发票）。**不能用于商用 POC 数据** |
| test-authoring/vehicle-complaint-component-tagger | https://huggingface.co/datasets/test-authoring/vehicle-complaint-component-tagger | `other`（卡片写明源数据许可：us-gov-public-domain） | datasets-server 约 1,123,239 行 / 约 884 MB；仓库含 2015–2019、2020–2024、2025–2026 官方投诉 zip 的 2026-11-17 镜像 | 英 | 预览字段为 `text`；并附官方 `CMPL.txt` | 官方投诉的 HF 镜像，可作离线副本 | 不是比官方更新的源；不要把 zip 提交进业务仓库。完整历史仍应回 NHTSA 日更文件 |
| Muhammmadd/iso26262-automotive-safety-requirements | https://huggingface.co/datasets/Muhammmadd/iso26262-automotive-safety-requirements | MIT | 955 行，约 0.62 MB | 英 | `messages` | 功能安全需求 | 卡片写明为 **合成** 基准数据，不是售后工单 |
| renumics/synthetic-vehicle-fleet-telemetry | https://huggingface.co/datasets/renumics/synthetic-vehicle-fleet-telemetry | CC-BY-SA-4.0 | server 登记约 843 行量级（多表 parquet 分区，实际信号文件更多） | 英 | 车队/行程/信号维表 | 遥测 schema 参考 | **合成数据**，且 CC-BY-SA 有 share-alike；优先用真实 Opel PID 集看字段 |
| sparks-solutions/AutomotiveUI-Bench-4K | https://huggingface.co/datasets/sparks-solutions/AutomotiveUI-Bench-4K | CC-BY-4.0 | 998 张图 / 4,208 条标注 | 德、英 | `image, box, class, test_action, expectation, conclusion, language, brand` | 车机 UI 评测，离售后知识库远 | 15 个品牌 2018–2025 IVI 交互基准 |
| ron164/automotive_requirements | https://huggingface.co/datasets/ron164/automotive_requirements | Apache-2.0 | 47 行 | 英 | 需求 ID、ASIL、验证方法等 | 需求工程 | eCall 连通性需求样例，离售后远 |
| pjaekae/automotive_engineering | https://huggingface.co/datasets/pjaekae/automotive_engineering | Apache-2.0 | 592 行 | 英 | 利益相关方需求 / 系统需求 / 架构 / V&V | 需求 | 卡片写明 GPT-3.5 **合成数据** |
| jinaai/automobile_catalogue_jp | https://huggingface.co/datasets/jinaai/automobile_catalogue_jp | 见卡片 | 中 | 日 | 车型目录 | 车型主数据弱信号 | 非诊断 |

---

## 4. 非 HF 的关键官方源（已打开页面或文件）

以下单独标注为 **非 Hugging Face**。只列本次核实可访问的。

1. **美国 NHTSA ODI 开放数据与 API（首选）**  
   - 门户：[https://www.nhtsa.gov/nhtsa-datasets-and-apis](https://www.nhtsa.gov/nhtsa-datasets-and-apis)（本次环境对 nhtsa.gov 首页有时返回 403，但同一目录内容已由检索与 `static.nhtsa.gov` 文件核对；data.gov 条目可打开）。  
   - 投诉平面文件：https://static.nhtsa.gov/odi/ffdd/cmpl/FLAT_CMPL.zip （目录约 360 MB，2026-11-23 05:08 ET / 18:08 中国时区更新）；字典 https://static.nhtsa.gov/odi/ffdd/cmpl/CMPL.txt （2026-05-01 更新，含字段 50–51）。投诉自 1995-01-01 起，TAB 分隔。关键字段包括 `CMPLID, ODINO, MFR_NAME, MAKETXT, MODELTXT, YEARTXT, CRASH, FAILDATE, FIRE, INJURED, DEATHS, COMPDESC, VIN, MILES, CDESCR, CMPL_TYPE` 以及经销商与操作人等。一行是「投诉 × 部件」，同一 `ODINO` 会重复。  
   - 召回：https://static.nhtsa.gov/odi/ffdd/rcl/FLAT_RCL_POST_2010.zip （HEAD Content-Length 15,069,192 字节，约 14 MB，2026-11-23 08:03:41 GMT / 16:03 中国时区）与 `FLAT_RCL_PRE_2010.zip`；字典 `RCL.txt`。  
   - 缺陷调查（1972 年起）：https://static.nhtsa.gov/odi/ffdd/inv/FLAT_INV.zip 与 [INV.txt](https://static.nhtsa.gov/odi/ffdd/inv/INV.txt)（字段 `NHTSA ACTION NUMBER, MAKE, MODEL, YEAR, COMPNAME, MFR_NAME, ODATE, CDATE, CAMPNO, SUBJECT, SUMMARY`）。目录页 `.../inv/` 本身 404，文件路径有效。  
   - 许可证：美国政府作品，公有领域；data.gov 投诉资源记 `us-pd`。不得暗示 NHTSA 背书。隐私字段必须在接入前剥离或哈希。  
   - API（`api.nhtsa.gov`，如按年款/品牌/车型查投诉）本次 HEAD 返回 403，**不把 API 写成已验证可用通道**；平面文件下载已验证。

2. **中国市场监管总局缺陷产品召回信息公开（中文官方召回公告，不是平面库）**  
   - 总局召回栏目（已打开，近期公告至 2026-11-20）：https://www.samr.gov.cn/zlfzj/qxcpzh/index.html  
   - 缺陷产品召回技术中心（已打开，含机动车召回公告、缺陷线索报告、召回查询、汽车三包查询入口）：https://www.samrdprc.org.cn/  
   - 栏目同时给出查询与线索渠道（www.dpac.gov.cn、公众号 SAMRDPAC 等）。**未核实到类似 NHTSA 的每日批量平面文件**；适合作为中文召回公告与法规的官方出处，不适合直接当结构化训练表。车主 VIN 查询页存在，本次任务不应采集或存储 VIN 查询结果。

未列入：欧洲 Safety Gate、Transport Canada 等——本次未做同等页面核实，故不写进推荐。厂商通讯 / TSB 在 NHTSA 目录中有「Recall Communications」一类大文件，但本次尝试的若干 `mfrcm` / `tsb` 猜测路径为 404，**不把 TSB 全量包写成已核实可下地址**。

---

## 5. Gated、空仓库、本次不推荐或未列入「可用」的集合

| 集合 | 状态 | 说明 |
|---|---|---|
| [AI4Manufacturing/automotive_engineering_qa_training](https://huggingface.co/datasets/AI4Manufacturing/automotive_engineering_qa_training) | **gated=manual**；Hub 200，README/info 401 | 仓库有 parquet 与 LICENSE/NOTICE，但未授权无法读卡片与样本。需要的话另走 HF 门禁申请，本次不当作可用数据 |
| emperor-mew/nhtsa-complaints、nhtsa-recalls、nhtsa-investigations、nhtsa-recall-completion | Hub 200，但几乎只有 README，datasets-server 500，0 行 | 卡片指向 MORVS 外部目录；**HF 上不可下载数据**。投诉卡片称高严重度约 21.3 万条，未在 HF 核实 |
| razaulhaq/nhtsa_complaints | MIT 标签，但仅 README，info 500 | 不可用 |
| thrsjay/elite-automotive-bdc-conversations | Apache-2.0，空集（EmptyDatasetError） | 不可用 |
| derabyte/mechanic-gpt | README 404，info 500 | 不可用 |
| YashKukreja23/NHTSA-CISS-2017-to-2024 | 无 README，viewer 无行 | 存在但无法核字段，不列入可用 |
| MatthewsFace/diagnosticar-es | 无许可证、README 404 | 虽有 255 行预览，许可不明，不用 |
| Growing-Moss 样品 | 可下载但许可证禁止商用与再分发 | 只可作字段形状参考 |
| williamTLmiller 样品、CJJones / Janukshan 诊断样本 | CC-BY-NC-4.0 | 商用 POC 不要当作可分发数据 |

检索时大量「DTC / recall / PID / diagnostic / automobile」命中被排除，例如 LLM 记忆基准、医学诊断、安检影像 PIDray、金融 automobile receivables、棋类等，与车企售后无关。

---

## 6. 使用建议（给 v3.0 数据先行）

1. 先剖面官方 NHTSA 投诉 + 召回 + 调查的字段与受控词（部件名、投诉来源码、召回类型），形成英文投诉/召回侧的候选类与槽位；同步剥离 VIN 与联系人字段。  
2. 用 `wushan/vehicle_qa` 做中文问诊/报告字段对照，看中英「现象—对话—结论」差在哪里。  
3. 用 `obd2-codes` + MechanicDB 样本建立 DTC 与处理方案的候选属性；不要把第三方码描述写成「官方 J2012」。  
4. 用 IndustryInstruction 汽车子集归纳中文用户问题类型（只作能力命名线索，不预写成 CAP 目录）。IndustryCorpus / Corpus2 只在需要中文汽车文档 RAG 时按需抽样，不要整包入库。  
5. 仍缺的 8D、保修工单、寻车 App 反馈、汽车之家语料、厂内维修手册，继续等脱敏样本；不要用合成诊断微调集或 NC 样品填进正式本体。

核查截止：2026-11-24，Asia/Shanghai。规模与更新时间以当日 Hub API、datasets-server 与官方 HEAD / 目录为准；官方投诉行数未直接下载清点。
