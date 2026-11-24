# Honda CR-V / Accord 2018 试验 step2：补硬键 + 细粒度部件对齐

测量时间：2026-11-24（Asia/Shanghai）  
范围：公开数据试验。不输出车辆识别号、个人信息或投诉叙述原文。私有工单数据未公开。  
产出目录：本仓库相对路径 `docs/`、`figs/`、`scripts/`。

---

## 一句话结论

公开侧真正新增的硬键，是召回平面文件里的 **OEM 零件号**（纠正字段偏移后，8 次召回中 6 次有号，143 条 campno↔零件号硬边）。厂商通信（TSB）平面文件可以按车型年读到 523 条通告，但 **通告号/厂内召回号/零件号都对不上** 本切片的召回，新增 TSB↔召回硬边为 **0**。投诉、调查仍然没有官方召回号。

标准词表对齐（用完整 COMPDESC 路径，不再只用主类）把投诉↔召回候选从 **2583 降到 56**（降 97.8%）。新抽检 10 条：接受 5、拒绝 3、存疑 2（可判死 5/8），对比 step1 的 2/10、可判死 2/4。调查候选降幅小（1516→1177），因为本切片大量投诉与调查共享同一条深度为 2 的「自动紧急制动」官方标签。

私有工单数据未公开，本文件只报告公开数据侧的结论与数字。

---

## 方案 1a：公开硬键

### 核实到的可访问源

| 源 | 状态 | 对本切片的硬键 |
| --- | --- | --- |
| `https://static.nhtsa.gov/odi/ffdd/tsbs/TSBS.txt` + `TSBS_RECEIVED_2015-2019/2020-2024/2025-2026.zip` | 可访问（2026-11-23 更新） | 有 `NHTSA ID`、`TSB/Document ID`、`Make/Model/Year`、`NHTSA Components`。**没有**与召回号的官方外键。 |
| 同目录 `MFR_COMMS_RECEIVED_*.zip` | 可访问，但是精简 CSV（通告号+车型年+摘要），键比 TSV 更少 | 未单独用来建边 |
| NHTSA API `recallsByVehicle` / `complaintsByVehicle` / `recalls/campaignNumber` | 可访问 | 召回有 `NHTSACampaignNumber`+部件，投诉有 `odiNumber`+部件。**没有**召回号、通告号、零件号。投诉 API 含 VIN 与叙述，本轮不落盘。 |
| `api.nhtsa.gov/tsbs/...` 及若干 TSB API | **403** | 未用 |
| 召回 PDF：`https://static.nhtsa.gov/odi/rcl/{year}/{PREFIX}-{camp}-{suffix}.pdf` | 目录不列文件，suffix 不能从召回号推导，不能系统抓取 | 不是结构化源。网上能搜到个别 20V771 文档（如 `RCMN-20V771-6490.pdf`、`RCRIT-20V771-7126.pdf`、`RCONL-20V771-6613.pdf`），文中有 Honda 活动号 X95、服务通告 20-039、零件 38808-/38800- 系列，但这些字 **没有** 出现在 FLAT_RCL 的公告号字段里，且 TSB 文件中 **没有** `A20-039`。 |
| FLAT_RCL 字段 24–27（纠正偏移后） | 已在本地召回平面文件中 | **可用硬键**：`MFGCAMPNO`、`RCL_CMPT_ID`、`MFR_COMP_NAME`、`MFR_COMP_PTNO` |

先前误测 `mfrcm/FLAT_MFRCM.zip` 为 404，是路径猜错。正确目录是 `odi/ffdd/tsbs/`。

### 本田 2018 CR-V / Accord（含 Accord Hybrid 行）实测

厂商通信 TSV（2015–2026 收到窗口）：

- 扫描 5,347,955 行，Honda 任意年 29,442 行，本切片车型年 **906 行**
- 独立通信 **523** 条 NHTSA ID、**466** 个 TSB/Document ID
- 类型：Service Bulletin/Repair Instructions 842 行，Other 64 行
- 2024 年新增字段在本切片中全空：`Mfr Internal Campaign ID / Software Version`、`Mfr Component System`、`Mfr Component Subsystem` 占用率 **0**
- 摘要里用正则挖 NHTSA 召回号、Honda 5-3-3 零件号：占用率 **0**
- 文档号形态以 Honda 内部号为主（如 `A18-006`、`A20-036`、`A20-043`），**没有** `A20-039`，也没有 `X95` / `K2G` / `KGC` 等厂内召回号

召回平面文件（纠正 0 基偏移：`[23]=RCL_CMPT_ID`，`[24]=MFR_COMP_NAME`，`[25]=MFR_COMP_DESC`（经常是零件适用车型），`[26]=MFR_COMP_PTNO`，`[27]/[28]=Do Not Drive / Park Outside`）。第一步曾把 `[27]` 的 Yes/No 误当成零件号，已改正。

| 召回号 | 厂内号 MFGCAMPNO | 结构化零件号（放宽 Honda 料号形态后） | 备注 |
| --- | --- | --- | --- |
| 18V629000 | K2G, V2F | 0（2018 年记录，零件字段为空） | 倒车摄像头软件，无 OEM 料号 |
| 18V663000 | C2N, P2O | 0 | 电动助力转向，官方受影响约 54 辆 |
| 20V314000 | （空） | 12；其中 `MFR_COMP_DESC=Accord` 对应 **17045-TVC-A03** | 燃油泵 |
| 20V771000 | **X95** | 32（BCM `38800-TVA-...` 等） | 厂内号有了，但 TSB 字段对不上 |
| 21V215000 | MULTIPLE CODES（非可用键） | 27（含 CR-V 的 17045-T2A-A01 等） | 燃油泵 |
| 23V158000 | BDC, MDD, NDA, QDB | 36（安全带锁扣，如 04813-TLA-A10ZC） | `MFR_COMP_NAME=Buckle Set L / Buckle Set R` |
| 23V858000 | KGC, KGD | 34（如 17708-TVA-A01-M1、17708-TVC-A030-M1）；描述字段写的是总成名而非车型，不能按车型过滤 | 燃油泵 |
| 26V332000 | REFER TO COMMENTS（非可用键） | 2（81167/81168-T2F-L012-M1） | 座椅重量传感器 |

### 新增硬边

- **TSB ↔ 召回（标识相等）: 0**
- **召回 ↔ OEM 零件号: 143** 条 `(campno, part_number)`（6/8 次召回，135 个不重复料号）
- 通告与召回在完整 COMPDESC 上的路径重合：15 对通信–召回（主要是 20V771 的雨刷/除雾/灯光等覆盖件），**只算词汇重叠，不算硬键**
- 投诉 ↔ 召回 / 调查：仍无 CAMPNO，硬边仍为 0
- NHTSA API 相对平面文件 **没有** 多出通告号或零件号

step1 原有硬边 123（DTC↔维修步骤 46 + 步骤↔MechanicDB 零件 77，调查 CAMPNO 仍为 0）加上本轮 143，合计 **266**。MechanicDB 零件是售后通用名，与 OEM 料号对不上。

---

## 方案 2：标准词表对齐与候选重算

对齐规则：

- 以 NHTSA 完整 COMPDESC 路径（`:` 分层）为规范层级；L1 只做有限别名（如 `FUEL/PROPULSION SYSTEM`、`FUEL SYSTEM, GASOLINE` → `FUEL SYSTEM`；`ENGINE` → `ENGINE AND ENGINE COOLING`）
- **细粒度候选**：官方标签原文完全相同（`exact_raw`，允许深度 1），或别名后的父子/公共前缀且共享深度 ≥ 2
- **主类相同但不到 2 层** 的旧匹配一律剔除
- DTC 按公开可见的 SAE J2012/OBD 系统组（P00–P0C 等前缀，不是照抄标准正文）映到规范路径；MechanicDB 零件名、vehicle_qa 中文词用关键词表映到更细路径

本切片规范路径 106 条；深度分布：1 层 3670 行、2 层 1212、3 层 314、4 层 19。投诉大量停在主类，召回往往写到 2–3 层，这正是旧候选虚高的原因。

### 前后对比

| 指标 | step1（主类） | step2（细粒度） | 变化 |
| --- | --- | --- | --- |
| 投诉↔召回候选 | 2583 | **56** | −97.8%（另有 2527 条被标成 L1-only 剔除） |
| 投诉↔调查候选 | 1516 | **1177** | −22.4%（另剔除 339） |
| 其中召回细匹配构成 | — | exact_raw 48，prefix≥2 为 6，公共前缀≥2 为 2 | |
| QA↔部件（词表） | 554 | 细词表能连上官方路径 217 / 301 帖 | 口径变严 |
| 投诉↔DTC（叙述正则，不存原文） | 253 | 253（未改） | — |
| 候选合计（替换 MMY+部件两项） | 4906 | **2040** | |
| 硬边 | 123 | 123（TSB+0）或 **266**（+143 OEM 料号） | |
| 硬/候选比 | 0.0251 | 0.0603（不加零件） / **0.1304**（加零件） | |

调查降幅小的原因：1177 条细匹配里 1094 条是官方标签完全相同的 `FORWARD COLLISION AVOIDANCE: AUTOMATIC EMERGENCY BRAKING`（深度 2）。本切片三条调查里有两条就是 AEB 主题，投诉也大量使用同一标签，所以细规则几乎留住了它们。这是标签本身已经够细，不是规则失效。

安全带召回 23V158 在细规则下 **0 条** 投诉候选（投诉多为 `SEAT BELTS` 一层，召回是 `SEAT BELTS:FRONT:BUCKLE ASSEMBLY`）。step1 抽检里曾接受过这类主类匹配，现在被有意丢掉。

MechanicDB 449 个零件名关键词能映射 137（30.5%），多为「燃油泵/氧传感器」这类通用名，**没有** OEM 料号，连不上 FLAT_RCL 的 135 个零件。DTC 前缀可以给出系统层路径，但不能单独当投诉–召回硬键。

### 原 10 条在新规则下的去留

6 条留下，4 条退回 L1-only（含先前接受的「安全带主类↔锁扣总成」）。先前拒绝的两条精确路径（54 辆转向召回、BCM 召回列出的外部灯光）仍然留下——细路径解决不了「覆盖范围过小」或「症状覆盖件≠根因件」。

### 新抽检 10 条（只看部件字段和官方召回摘要）

接受 5 / 拒绝 3 / 存疑 2，可判死 5/8。对比 step1：2/10，可判死 2/4。两组样本不同，不能当成严格 A/B，但方向清楚：精确到叶子（摄像头、燃油泵）更好判；只共享到 `DELIVERY`（油管 vs 油泵）应拒；BCM 召回上的 `VISIBILITY/WIPER` 仍存疑。

---

## 更新后的链示例

**链 1（最完整，见新图）**  
`HONDA ACCORD 2018` → 投诉 ODINO **11519200** → 部件路径 `FUEL SYSTEM, GASOLINE:DELIVERY:FUEL PUMP`（exact_raw，抽检接受）同时指向：

- 召回 **20V314000**（厂内号空）→ 硬键 OEM 零件 **17045-TVC-A03**（描述字段写明 Accord）
- 召回 **23V858000**（厂内号 KGC, KGD）→ 硬键零件示例 **17708-TVA-A01-M1**、**17708-TVC-A030-M1**（该召回共 34 个料号，描述未按车型拆开）

这条链能演示「现象/部件路径 → 召回 → 官方零件号」。投诉侧仍然没有召回号，所以投诉–召回还是候选，不是硬边。

**链 2**  
投诉 ODINO **11324947** → `BACK OVER PREVENTION: SENSING SYSTEM: CAMERA` → 召回 **18V629000**（厂内号 K2G, V2F，抽检接受）。2018 年该记录的 `MFR_COMP_PTNO` 为空，链在零件处断开。

**断点链（20V771）**  
投诉 `VISIBILITY/WIPER` 可以 exact_raw 对上召回 **20V771000**（厂内号 X95，32 个 BCM 零件号是硬的），但抽检为存疑：这是覆盖症状件，不是 `ELECTRICAL SYSTEM:BODY CONTROL MODULE:SOFTWARE`。网上能搜到通告 20-039，平面文件里对不上，TSB↔召回硬边为 0。

图：`figs/chain_odino_11519200_fuel_pump.png`

---

## 坦白断点

1. 投诉、调查没有官方召回号/通告号；调查 CAMPNO 在本切片仍全空。
2. 厂商通信拿得到通告实体和部件标签，拿不到与召回/投诉的标识级外键；2024 新字段在本历史切片为空。
3. 召回 PDF 不是可系统使用的结构化源；偶然找到的 20-039 也没出现在 TSB 文件里。
4. OEM 零件号是真实硬键，但 2018 年两条召回没有号；有的描述是车型、有的是总成名，不能一律按车型过滤；与 MechanicDB 对不上。
5. 细规则大幅降低召回候选，但消灭不了「路径对、范围不对」（54 辆转向）和「症状覆盖件」（BCM–雨刷）。安全带这类「投诉只写主类」会被丢掉，召回覆盖变窄。
6. 中文 QA、DTC 前缀、零件词表仍然是规则候选，需要人工抽检，不是硬边。

---

## 主要文件

- 公开源占用率与连接结果由 `scripts/extract_public_keys.py` 写入本地 `data/`（不提交）
- 纠正后的召回零件由 `scripts/fix_rcl_parts_and_rejoin.py` 写入本地 `data/`（不提交）
- 厂商通信结构字段（无摘要正文）同样写入本地 `data/`（不提交）
- 细粒度对齐与候选重算由 `scripts/align_and_rematch.py` 写入本地 `data/`（不提交）
- 抽检 10 条的判断已写在本文表格中
- `figs/chain_odino_11519200_fuel_pump.png`
