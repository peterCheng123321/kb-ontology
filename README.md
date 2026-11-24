# 车企售后知识库本体 POC

用公开数据搭建一套可串联的售后知识库本体，技术路线为 **LinkML → RDF/Turtle → Apache Jena Fuseki**。

本仓库只放：技术栈说明、本体模式、处理公开数据的脚本、本田 CR-V / 雅阁 2018 试验报告，以及由公开数据生成的关系图。第三方原始数据文件不提交，请按下面的链接自行下载。

私有工单数据未公开。

## 目标

- 把投诉、召回、调查、部件、故障码、维修步骤和零件建成可查询的关系图。
- 每条关系标明是官方硬连接，还是带方法、分数、审核状态的候选关联。
- 演示默认只展示硬连接和抽检通过的候选，不把「同车型有过召回」当成已确认的追溯。

本田 2018 切片上的试验结果（详见 [docs/TRIAL-RESULTS.md](docs/TRIAL-RESULTS.md) 与 [docs/STEP2-RESULTS.md](docs/STEP2-RESULTS.md)）：

- 硬连接可以串起「故障码 → 维修步骤 → 零件」，以及「召回 → 原厂零件号」。
- 「投诉 → 召回」没有官方外键，只能按年款车型加部件做候选；用细粒度部件路径后，候选从 2,583 条降到 56 条。
- 调查到召回的官方硬键在该切片上为 0（三条调查均未填写召回号）。

## v3.0 技术栈

完整裁定见 [docs/ONTOLOGY-TECH-STACK-v3.md](docs/ONTOLOGY-TECH-STACK-v3.md)。要点：

| 层 | 选用 | 钉死版本（2026-11-24 核对） |
|---|---|---|
| 建模源 | LinkML（唯一手写源） | 1.12.1，Python 3.12 |
| 序列化 | Turtle（OWL 2 的 RDF 序列化） | RDF 1.1 兼容 |
| 三元组库 | Apache Jena Fuseki + TDB2 | 6.3.0，需 Java 21+ |
| 推理 | 运行时 OWL 2 RL；发布时 OWL 2 DL / HermiT | 经 ROBOT 1.9.11 |
| 校验 | SHACL + pySHACL | pySHACL 0.40.2，RDFLib 7.6.0 |

能力、类和字段从数据观察得出，不预先规定一整张能力表。文档里规划的完整目录（`src/linkml/` 等）是目标布局；本仓库当前先放入试验模式、形状、脚本与报告。

可选的文档检索可对接开源 [Tencent/WeKnora](https://github.com/Tencent/WeKnora) v0.9.0，检索命中须带知识库标识才能提升结构化证据级别。本仓库不包含检索服务配置或凭证。

## 目录结构

```
kb-ontology/
  README.md                 本文件（含数据链接与许可证）
  LICENSE                   本仓库代码与文档：Apache-2.0
  NOTICE                    第三方数据署名与许可证提示
  requirements.txt          本体工具链依赖
  docs/                     技术栈、数据核查、演示方案、试验报告
  schema/                   LinkML 手写源，以及由其生成的 OWL
  shapes/                   SHACL 形状
  scripts/                  下载公开数据、构建试验图、对齐部件路径
  queries/                  试验用 SPARQL
  figs/                     由公开数据生成的关系图（图中无车辆识别号）
  data/                     本地下载目录，已列入 .gitignore，不提交
  gen/                      本地生成物，不提交
```

## 数据来源、直接链接与许可证

下列链接在 2026-11-24（Asia/Shanghai）核对。`static.nhtsa.gov` 与 Hugging Face 数据集页返回 HTTP 200。官方门户 https://www.nhtsa.gov/nhtsa-datasets-and-apis 是 NHTSA 公开的数据集说明页；部分网络环境对该门户会返回 403，但不影响下面的直接文件链接。第三方原始文件请下载到本地 `data/`，不要提交到 git。

使用公开投诉数据时：车辆识别号、城市州、经销商、车辆操作人、叙述原文不得写入本仓库或对外演示库；文档只写字段名，不写取值。

### 美国 NHTSA（公有领域）

官方说明：[NHTSA Datasets and APIs](https://www.nhtsa.gov/nhtsa-datasets-and-apis)

许可证：美国政府作品，公有领域（Public Domain, U.S. Government）。可用于 POC 与商用，但须遵守隐私限制，且不得暗示官方背书。

| 文件 | 直接链接 | 用途 |
|---|---|---|
| 投诉平面文件 `FLAT_CMPL.zip` | https://static.nhtsa.gov/odi/ffdd/cmpl/FLAT_CMPL.zip | 车主投诉（按 `ODINO` 归并）、部件、年款车型、结构化结果字段 |
| 投诉字段字典 `CMPL.txt` | https://static.nhtsa.gov/odi/ffdd/cmpl/CMPL.txt | 投诉表字段说明 |
| 2010 年后召回 `FLAT_RCL_POST_2010.zip` | https://static.nhtsa.gov/odi/ffdd/rcl/FLAT_RCL_POST_2010.zip | 召回活动、缺陷与纠正措施、覆盖车型、原厂零件号 |
| 2010 年前召回 `FLAT_RCL_PRE_2010.zip` | https://static.nhtsa.gov/odi/ffdd/rcl/FLAT_RCL_PRE_2010.zip | 全量召回中的历史部分（匹配率统计用） |
| 召回字段字典 `RCL.txt` | https://static.nhtsa.gov/odi/ffdd/rcl/RCL.txt | 召回表字段说明 |
| 缺陷调查 `FLAT_INV.zip` | https://static.nhtsa.gov/odi/ffdd/inv/FLAT_INV.zip | 调查行动、主题、可选的召回号 `CAMPNO` |
| 调查字段字典 `INV.txt` | https://static.nhtsa.gov/odi/ffdd/inv/INV.txt | 调查表字段说明 |

厂商通信 / 技术服务通告（TSB）平面文件位于同一官方前缀下。该目录本身不提供文件列表，请使用下面已核对可下载的直接链接：

| 文件 | 直接链接 | 用途 |
|---|---|---|
| TSB 字段字典 `TSBS.txt` | https://static.nhtsa.gov/odi/ffdd/tsbs/TSBS.txt | 厂商通信字段说明 |
| `TSBS_RECEIVED_2015-2019.zip` | https://static.nhtsa.gov/odi/ffdd/tsbs/TSBS_RECEIVED_2015-2019.zip | 2015–2019 年收到的技术服务通告 |
| `TSBS_RECEIVED_2020-2024.zip` | https://static.nhtsa.gov/odi/ffdd/tsbs/TSBS_RECEIVED_2020-2024.zip | 2020–2024 年收到的技术服务通告 |
| `TSBS_RECEIVED_2025-2026.zip` | https://static.nhtsa.gov/odi/ffdd/tsbs/TSBS_RECEIVED_2025-2026.zip | 2025–2026 年收到的技术服务通告 |
| `MFR_COMMS_RECEIVED_2015-2019.zip` | https://static.nhtsa.gov/odi/ffdd/tsbs/MFR_COMMS_RECEIVED_2015-2019.zip | 同期厂商通信精简表 |
| `MFR_COMMS_RECEIVED_2020-2024.zip` | https://static.nhtsa.gov/odi/ffdd/tsbs/MFR_COMMS_RECEIVED_2020-2024.zip | 同期厂商通信精简表 |
| `MFR_COMMS_RECEIVED_2025-2026.zip` | https://static.nhtsa.gov/odi/ffdd/tsbs/MFR_COMMS_RECEIVED_2025-2026.zip | 同期厂商通信精简表 |

在本田 2018 试验中，通告可以按车型年读到，但通告号与召回号对不上，没有新增硬连接。

### Hugging Face 数据集

| 数据集 | 直接链接 | 许可证 | 用途 |
|---|---|---|---|
| wushan/vehicle_qa | https://huggingface.co/datasets/wushan/vehicle_qa | Apache-2.0 | 中文故障问诊与诊断对话；按品牌、车型、部件词表做弱关联 |
| CodesList/obd2-codes | https://huggingface.co/datasets/CodesList/obd2-codes | CC BY 4.0（需署名） | OBD-II / DTC 词表（代码、描述、类别、严重度）。第三方汇编，不是 SAE J2012 官方文本 |
| Ichlibitiche/mechanicdb-obd2-repair-sample | https://huggingface.co/datasets/Ichlibitiche/mechanicdb-obd2-repair-sample | ODbL 1.0（署名 + 相同方式共享） | 故障码到维修步骤、零件、工时的样本关系。完整库另行收费；再分发派生库须保持相同许可 |
| BAAI/IndustryInstruction_Automobiles | https://huggingface.co/datasets/BAAI/IndustryInstruction_Automobiles | Apache-2.0 | 中英汽车领域指令问答，辅助能力用语，也可作检索语料，不是结构化工单 |
| BAAI/IndustryCorpus_automobile | https://huggingface.co/datasets/BAAI/IndustryCorpus_automobile | Apache-2.0 | 汽车领域网页语料，适合作为检索文档，噪声较大，不宜单独推导字段 |
| BAAI/IndustryCorpus2_automobile | https://huggingface.co/datasets/BAAI/IndustryCorpus2_automobile | Apache-2.0 | 上述语料的后续版本，用途相同 |
| PedroCuisinier2025/OBD2_panel_opel_2012 | https://huggingface.co/datasets/PedroCuisinier2025/OBD2_panel_opel_2012 | 以数据集卡片为准 | 真实 OBD-II PID / 遥测字段形状（转速、车速、水温等），用于冻结帧或实况数据槽位，不是投诉或召回 |

更完整的核查表、匹配率与不适用数据说明见 [docs/PUBLIC-DATASETS-HF.md](docs/PUBLIC-DATASETS-HF.md)。关系库方案见 [docs/DEMO-RELATIONAL-DB-PLAN.md](docs/DEMO-RELATIONAL-DB-PLAN.md)。本仓库代码与文档为 Apache-2.0；第三方数据不随仓库分发，见 [NOTICE](NOTICE)。

## 如何下载公开数据并复现试验

需要 Python 3.12+。建议使用虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

1. 下载公开数据（默认只取字段字典等小文件；大型平面文件加 `--fetch-large`）：

   ```bash
   python scripts/download_public_data.py            # 只下载字段字典并打印全部直接链接
   python scripts/download_public_data.py --fetch-large
   ```

   文件会落到 `data/raw/`（该目录不进 git）。也可按上一节表格用浏览器或 `curl` 直接下载。

2. 按 [docs/DEMO-RELATIONAL-DB-PLAN.md](docs/DEMO-RELATIONAL-DB-PLAN.md) 的切片规则，从投诉、召回、调查平面文件中抽出本田 CR-V / 雅阁 2018，并与 CodesList、MechanicDB 样本、`vehicle_qa` 对齐，写入 `data/honda-2018/`。切片中不要保留车辆识别号或投诉叙述原文。

3. 构建试验图并做校验、查询（需先有步骤 2 的切片）：

   ```bash
   python scripts/build_trial.py
   python scripts/run_queries_and_shacl.py
   ```

4. 补召回原厂零件号、按细粒度部件路径重算候选：

   ```bash
   python scripts/extract_public_keys.py
   python scripts/fix_rcl_parts_and_rejoin.py
   python scripts/align_and_rematch.py
   ```

5. 若要加载到 Jena Fuseki 6.3.0，将生成的 Turtle（TBox + 审过的 ABox）导入 TDB2。TDB2 数据目录不要提交到 git。试验报告中的数字是在 RDFLib 内存图上复现的；当时未启动 Fuseki。

关系图：

- [figs/chain_odino_11407338.png](figs/chain_odino_11407338.png)：CR-V 2018 投诉 `11407338`，从燃油系统走到故障码、维修步骤、零件，旁路召回候选与无召回号的调查。
- [figs/chain_odino_11519200_fuel_pump.png](figs/chain_odino_11519200_fuel_pump.png)：雅阁 2018 投诉 `11519200`，经细粒度「燃油泵」路径连到召回与原厂零件号。

## 本仓库不包含什么

- 第三方原始数据文件（NHTSA 平面文件、码表、维修样本、问诊全文等）
- 未公开的业务数据、车辆识别号、人名或叙述原文
- 密钥、凭证，以及检索服务的部署配置
