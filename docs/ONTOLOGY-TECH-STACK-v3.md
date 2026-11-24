# 知识库本体：技术栈、核心技术与文件（POC 草案 v3.0）

- **文档状态**：POC 草案 v3.0（2026-11-24，东八区）。只锁定技术栈、核心技术与仓库文件布局。能力、类、字段、能力问题与形状内容**不再预先规定**。
- **定位**：面向车企售后知识库的本体 POC。与检索服务、业务应用并列部署，不把三元组写进业务数据库，也不把本体源塞进检索服务。
- **与上一版关系**：v2.5 全文备份为同目录 `ONTOLOGY-CAPABILITIES-AND-FIELDS-v2.5.bak.md`（以及更早的 v1 与 v2.0–v2.4 备份）。其中的能力目录、类与字段表、能力问题清单、SHACL 形状内容、首个切片对象模型、S/O/D 等**只保留在备份中**，不再作为现行定义。v1 与各 `.bak` 均不改动。
- **本版不做**：不写代码、不提交仓库、不写入生产或转储、不打印密钥或车辆识别号。工具版本均按 2026-11-24 能公开核对的发布页钉死，来源见附录。

---

## 一、数据优先：能力与模型稍后从数据得出

能力、类和字段只有见到真实数据之后才能确定。本版不预设它们。

导出方法（见数据后再做，不在本文件展开模型）：先对真实来源做数据剖析（公开投诉与召回、授权样本、FAQ、日志与可能的诊断描述等：字段清单、取值形态、缺失率；报告中不出现识别号）→ 从高频规范化用语和结构化字段抽出候选术语 → 用真实案例写出能力问题 → 再写入 LinkML 类与属性，并生成 OWL / SHACL 与能力问题查询。用脱敏夹具做校验，不够再回到剖析，而不是先发明一套能力表。

---

## 二、技术栈（分层锁定）

### 2.1 建模源

**裁定**：唯一手写源是 **LinkML**（钉死 `linkml == 1.12.1`，发布于 2026-10-13；配套 `linkml-runtime >= 1.12.0`，Python `>= 3.10`，本仓库工具链使用 **Python 3.12**）。模式用 YAML 编写，经生成器产出 OWL/Turtle、SHACL、JSON-LD context 与 JSON Schema。仓库里不得另有一份与 LinkML 并行维护的手写 OWL 作为真源。

Protégé 只可用作浏览或抽查，不能当源。截至 2026-11-24，Protégé 6.0.0 仍为 alpha-1（2026-09-28），与 5.x 插件不兼容，更不宜作为源。

### 2.2 序列化

**裁定**：发布与交换的主序列化是 **Turtle**（OWL 2 的 RDF 序列化）。ROBOT / WIDOCO 若需要，可由 Turtle 再导出 RDF/XML 或 OWL/XML，这些都是构建产物。JSON-LD context 与 JSON Schema 同样由 LinkML 生成，供应用侧校验，不替代 OWL 发布物。

默认写出与 RDF 1.1 兼容的 Turtle，以便工具普遍可读。Apache Jena 自 6.1.0（2026-05-11）起支持 RDF 1.2 句法；若日后需要语句级再化器，再在生成配置中打开，见第五节。

### 2.3 三元组库

**裁定**：运行时三元组库为 **Apache Jena Fuseki + TDB2**，钉死 **Jena / Fuseki 6.3.0**（2026-11-22；https://jena.apache.org/download/ ）。Jena 6 要求 **Java 21+**。TDB2 是原生 RDF 存储；Fuseki 提供 SPARQL 查询、更新与图存储协议。POC 以单独进程（或容器）与检索服务、业务应用并列部署，不把 TBox/ABox 存进业务数据库。

TDB2 数据目录与 Fuseki 运行时状态不进 Git。

### 2.4 推理机与剖面

**裁定**：采用 OWL 2 剖面分工（W3C OWL 2 Profiles，2012-12-11 推荐标准，https://www.w3.org/TR/owl2-profiles/ ）：

- **运行时**：OWL 2 RL，由 Jena 规则引擎在 Fuseki 侧物化可判定的蕴含，供查询使用。不在请求路径上跑完整 DL 分类。
- **发布时**：OWL 2 DL，由 CI 调用 ROBOT 的 `reason --reasoner hermit` 做一致性与分类。超时默认 10 分钟即失败并要求拆分模块（模块如何拆，见数据规模后再定）。

不在运行时导入完整 BFO 公理集；上层对齐是发布政策，不是运行时依赖。

### 2.5 校验

**裁定**：完整性与约束用 **SHACL**。规范钉在 W3C SHACL 推荐标准（2017-07-20，https://www.w3.org/TR/shacl/ ）。执行器钉死 **pySHACL 0.40.2**（GitHub 发布 2026-10-26，https://github.com/RDFLib/pySHACL/releases ）。配套 **RDFLib 7.6.0**（2026-02-13）。

CI 对正例、反例夹具跑 pySHACL。形状文件大部分由 LinkML 生成；仅当生成器覆盖不到时，才允许在 `src/shacl/extras/` 手写补充形状，且必须在文档中说明补的是哪一类约束。

SHACL 1.2 各篇在 2026-11 仍为 Working Draft。本 POC **不依赖**尚未成为推荐标准的 1.2 专有特性。

### 2.6 工具与 CI

发布流水线（失败即阻断，顺序固定）：

1. `linkml` 从 YAML 生成 Turtle/OWL、SHACL、JSON-LD context、JSON Schema。
2. **ROBOT 1.9.11**（2026-10-01，https://github.com/ontodev/robot/releases ）做 `validate-profile`（RL 与 DL）、合并、报告（`robot report`）。
3. ROBOT 调用捆绑的 **HermiT** 做 DL 分类与一致性。不使用 Oxford 下载页仍标为 current 的 HermiT 1.3.8（2013）。Protégé 6 所用的 HermiT 1.5.0 是面向 OWL API 5.5.1 的重建，**不**作为本 CI 的钉死版本。
4. **OOPS!**（https://oops.linkeddata.es/ ，本体常见陷阱扫描）与 **FOOPS! v0.4.0**（2026-05-04，FAIR 检查，https://zenodo.org/records/20024871 ）出报告；P0 级陷阱阻断发布。不把 2026-07 的实验性 OOPS-Plus 当作门禁。
5. pySHACL 跑正反例。能力问题的 SPARQL 验收查询在**有真实数据并写出问题之后**才加入；本阶段流水线预留目录，不预制查询内容。
6. **WIDOCO 1.4.26**（2026-10-23，https://github.com/dgarijo/Widoco/releases/tag/v1.4.26 ）生成 HTML 文档，供 w3id 内容协商的 `text/html` 端。CI 使用其 JDK 17 可执行 JAR，运行在 JDK 21 上。

CI 使用 GitHub Actions，必须是本体仓库自己的工作流文件，不与应用测试混成一个不可拆的任务。

### 2.7 与检索服务、业务应用如何并列

三套系统并列，通过稳定标识与网络接口集成，而不是把本体塞进其中任一系统的数据库。

| 系统 | 职责 | 本 POC 如何对接 |
|---|---|---|
| 本体服务（Fuseki + TDB2） | 存发布后的 TBox 与已审 ABox，提供 SPARQL | 业务应用只读查询；发布由 CI 写入或加载 TDB2 |
| 检索服务（可选） | 文档与 FAQ 的检索（RAG） | 可对接开源 [`Tencent/WeKnora`](https://github.com/Tencent/WeKnora) **v0.9.0**（2026-10-29）。业务应用调用其检索 API |
| 业务应用 | 案件流程、权限、与一线交互 | 流程数据留在应用自己的数据库；需要术语、约束或已审事实时再查 Fuseki，需要文档命中时再查检索服务 |

业务应用不得把普通关系数据库当作三元组库，也不得把检索命中直接写成已发布术语。

### 2.8 RAG 链接

**裁定**：检索接地采用“本体术语 + 已链接文本块”的混合方式（已发表的混合 / OG-RAG 方向，不是工业标准）。链接的稳定锚是 WeKnora 能够返回的 **知识库标识 + 文档标识（knowledge_id）+ 内容修订（ContentRevision）**。分块标识只用于展示，不得当作跨重分块的稳定锚。公开源码表明 WeKnora **不保证**跨重分块的内容哈希或标题路径，因此不得把这类字段设计成 WeKnora 来源的必填重锚条件。

缺知识库标识的命中整条丢弃。未链接到已发布术语的命中可以展示，但不得单独抬高结构化结论。链接如何写入、候选如何确认，等见到数据与检索服务的实际返回后再规定，本文件只锁定锚点字段与这条门禁原则。

### 2.9 钉死的版本与运行位置

核对日期：2026-11-24（东八区）。

| 组件 | 钉死版本 | 在哪里运行 |
|---|---|---|
| Python（本体工具链） | 3.12 | 开发机与 CI 的工具环境 |
| LinkML | 1.12.1（runtime ≥ 1.12.0） | 开发机与 CI，生成发布物 |
| RDFLib | 7.6.0 | 开发机与 CI（pySHACL 依赖） |
| pySHACL | 0.40.2 | CI |
| JDK | 21（Temurin 或同等发行） | CI、Fuseki 进程 |
| Apache Jena / Fuseki / TDB2 | 6.3.0 | 独立服务（开发、测试、POC 运行环境） |
| ROBOT | 1.9.11 | CI |
| HermiT | ROBOT 1.9.11 捆绑的 `reason --reasoner hermit` | 仅 CI / 发布时 |
| WIDOCO | 1.4.26 | CI，产出静态文档 |
| FOOPS! | v0.4.0 | CI 或发布时调用其服务 |
| OOPS! | 公共服务（无产品版本号） | 发布时扫描 |
| WeKnora（可选对接） | 公开上游 v0.9.0 | 独立检索服务 |
| 业务应用 | 由部署方自行决定运行时 | 现有应用环境 |

### 2.10 IRI 与版本策略（只作为栈决策，不预置术语）

- 术语 IRI：`https://w3id.org/poc-kb/{module}/{kind}/{code}`（斜杠，可读短码，**不含版本**）。发布后永久，不以模块搬迁改写路径。
- 本体文档 IRI：`https://w3id.org/poc-kb/{module}/`；每次发布另给 `owl:versionIRI`，采用 SemVer 2.0.0，例如 `https://w3id.org/poc-kb/core/3.0.0`。`owl:versionInfo` 与 `versionIRI` 末段一致。
- 内容协商：同一术语或文档 IRI，按 `Accept` 返回 HTML（WIDOCO）或 Turtle/RDF。
- w3id 组织短码尚未正式注册。**默认**继续用占位基址 `https://w3id.org/poc-kb/`。一旦注册，旧基址做 301/303，不改已发布路径尾段。
- 领域短码（`kind`、`module`）等见到数据再定，本文件不预置业务类名。

### 2.11 上层与行业标准对齐政策（只作为栈决策，不预置内容）

- 上层：日后导出的类，对齐 **BFO 2020**（ISO/IEC 21838-2:2021，https://www.iso.org/standard/74572.html ）的范畴；运行时不导入完整 BFO 公理集。DOLCE 只作备选对照，不作为发布依赖。
- 行业：当数据中实际出现故障码、信号、诊断描述、场问题等对象时，再用 `alignments` 指到相应的公开或已授权标准词条（如 SAE J2012 / ISO 15031-6、ISO 14229、ODX / ISO 22901、SOVD / ISO 17978、COVESA VSS / VSSo、AIAG-VDA FMEA、8D/保修实践、以及适用范围内的 ISO 21448 / ISO 26262）。**不复制**收费标准正文或整份词表，不在未见数据前预建这些类。
- 对齐类型限于 SKOS 的 `exactMatch` / `closeMatch`、审慎的 `owl:equivalentClass`，以及仅供人参考的 `rdfs:seeAlso`。

---

## 三、核心技术与否决项

每项给出用途、采用理由，以及 1–2 个被否决的替代与原因。

| 选用 | 用途 | 为何用它 | 否决的替代 |
|---|---|---|---|
| LinkML 为唯一手写源 | 编写与评审本体模式，并生成多种产物 | 文本 YAML，可在 Git 中做差量评审；一次源可生成 OWL、SHACL、JSON Schema，避免各写各的 | **只在 Protégé 里建模**：二进制/GUI 为主，难以做 CI 真源；Protégé 6 仍为预发布。**以 Pydantic / JSON Schema 为真源**：无法稳定生成 OWL 与 SHACL |
| RDF / OWL 图 | 表达术语、公理与可对齐的行业标识 | 有国际标准的 IRI、SPARQL、OWL 剖面与 SHACL；便于与 VSS/VSSo、BFO 等外部词表对齐 | **Neo4j / 属性图为唯一库**：便于应用图遍历，但缺少 OWL/SHACL 与标准词表的一等地位，不利于主机厂知识库的发布与对齐。若应用侧以后要属性图，只能作为导出，不能当本体真源。**只用 Postgres 表存术语**：无原生 SPARQL/OWL |
| OWL 2 RL（运行时）+ OWL 2 DL / HermiT（发布时） | 运行时蕴含与发布时分类 | RL 是 W3C 可规则化的剖面，Jena 能跑，延迟可控；完整 DL 分类放在发布门禁，避免请求路径被分类器拖死 | **运行时只用 OWL DL / HermiT**：时延不可控。**只用 ELK**：针对 EL 剖面，不能检查本栈选定的 DL 发布公理，也不能替代 RL 规则库 |
| Jena Fuseki + TDB2 | 运行时 SPARQL 与持久化 | 开源、Apache 许可清晰、与 RL 规则和 TDB2 原生集成；6.x 仍在积极发布 | **Blazegraph**：已停止维护，不得作主库。**商业 GraphDB / Stardog 作 POC 必选**：能力更强但引入授权与绑定，POC 不需要；若以后运维有明确需求再评估。**RDFLib 或 Owlready2 当主库**：适合作测试夹具，不适合作为服务化 SPARQL 库 |
| SHACL + pySHACL | 完整性与发布约束 | 约束失败可定位到节点与形状，不靠 `rdfs:domain` 去改写类型；Python 工具链与 LinkML 生成物衔接顺畅 | **只用 OWL 开世界公理当完整性检查**：缺数据时不会失败，无法做发布门禁。**仅靠应用层 Pydantic**：约束进不了发布的图，也无法与 SPARQL 夹具共用 |
| ROBOT + WIDOCO + OOPS!/FOOPS! | 剖面校验、报告、文档与质量扫描 | 这是本体发布的常见 OntologyOps 组合，版本与许可都可公开核对 | **手工导出文档、无门禁**：无法重复验收。**用实验性 LLM 扫描器（OOPS-Plus）替代 OOPS!**：2026-07 的 0.0.01 仍偏实验，不进门禁 |

---

## 四、文件与目录布局

**裁定**：本仓库 `kb-ontology/` 与业务应用、检索服务配置**并列**，不把本体放进检索服务的源码树，也不把未公开业务数据放进本仓。当前目录先放入试验产物，下文 4.1 是目标布局。

命名一律小写短横线或下划线，不用空格；生成物文件名可带 SemVer，术语 IRI 本身仍不含版本。

### 4.1 目录树

```
kb-ontology/
  README.md
  LICENSE
  pyproject.toml                  # 本体工具链依赖（linkml、pyshacl、rdflib）
  Makefile                        # gen / validate / release 入口
  src/
    linkml/
      metadata.yaml               # 本体 IRI、前缀、version 注解（无业务类）
      prefixes.yaml
      catalog.yaml                # 模块导入清单
      # 业务模块 YAML 在见到数据后再增，例如日后的 aftersales.yaml
    mappings/
      alignment-policy.md         # 对齐类型与“不复制词表”的政策
      weknora-anchors.md          # 锚点字段与 WeKnora 返回的对应（kb / doc / revision）
    shacl/
      extras/                     # 仅存放生成器覆盖不到的手写补充形状
      README.md
    sparql/
      README.md                   # 日后放置能力问题查询，本阶段不预制内容
  tests/
    fixtures/
      README.md                   # 只允许占位符与公开编码，禁止识别号与原文
    shapes/                       # 日后的正反例图
    queries/                      # 日后的 CQ 验收查询
  ci/
    ontology.yaml                 # CI 工作流（视所用平台放在 ci/ 或 .github/workflows/）
    robot.sh                      # ROBOT 调用封装
    pins.txt                      # 钉死的工具版本（与本文第二节一致）
  docs/
    TECH-STACK.md                 # 可与本草案同步的栈说明
    iri-policy.md
    data-first-method.md
    w3id/
      .htaccess 或 _config        # 待注册的重定向规则草稿
  gen/                            # 构建产物（见 4.3）
  release/                        # 发布产物（见 4.3）
  scripts/
    generate.sh
    release.sh
```

Fuseki 的配置样例可放在 `docs/fuseki/`（无密钥、无生产数据路径）。TDB2 库本身放在部署环境，例如 `/var/lib/fuseki/databases/poc-kb/`，不在本仓库。

### 4.2 手写还是生成

| 路径 | 格式 | 手写 / 生成 | 是否进 Git |
|---|---|---|---|
| `src/linkml/*.yaml` | YAML（LinkML） | 手写，唯一模式真源 | 是 |
| `src/mappings/*.md` | Markdown | 手写政策 | 是 |
| `src/shacl/extras/` | Turtle（SHACL） | 手写补充，须说明理由 | 是（若有） |
| `src/sparql/`、`tests/queries/` | SPARQL | 见数据并写出能力问题后再手写 | 目录进 Git；内容见数据后补 |
| `tests/fixtures/` | Turtle 或 LinkML 实例 YAML | 手写脱敏夹具 | 是，但禁止真实识别号、原文、密钥 |
| `ci/`、`Makefile`、`pyproject.toml`、`scripts/` | YAML / 壳脚本 / TOML | 手写 | 是 |
| `docs/`（政策与栈说明） | Markdown | 手写 | 是 |
| `docs/w3id/` | 重定向配置 | 手写草稿 | 是（不含私钥） |
| `gen/owl/poc-kb.ttl` 等 | Turtle / OWL | **生成** | 默认不进主干；发布标签可附快照，见下 |
| `gen/shacl/poc-kb.shacl.ttl` | Turtle | **由 LinkML 生成** | 同上 |
| `gen/context/poc-kb.context.jsonld`、`gen/jsonschema/` | JSON-LD / JSON Schema | **生成** | 同上 |
| `release/snapshots/{version}/poc-kb.ttl` | Turtle | **生成的发布快照** | **默认在打发布标签时提交**，便于复现 |
| `release/widoco/` | HTML | **生成** | 否（由 CI 发布到文档托管） |
| `release/reports/`（robot report、HermiT 日志、OOPS!/FOOPS! 输出） | TSV / 日志 / JSON | **生成** | 默认否；发布标签可附带摘要 |
| TDB2 数据目录、Fuseki 运行时 | 二进制库 | 运行时生成 | **否** |
| 密钥、凭证、未公开业务原文与标识信息 | 任意 | 外部数据 | **否，永不进本仓** |

### 4.3 生成与发布约定

- 开发时在本地或 CI 写入 `gen/`，`gen/` 列入 `.gitignore`。
- 每次正式发布：在 `release/snapshots/{x.y.z}/` 落下当时的 Turtle/OWL 快照与 `owl:versionIRI`，随 Git 标签保存；WIDOCO 站点发布到文档托管，由 w3id 跳转，不把整个站点塞进主干。
- 破坏性变更须保留旧术语 IRI，并用后续模型中的替代关系指向新术语；具体关系名见数据后再定，本栈只要求“不删 IRI、不把版本写进术语路径”。

---

## 五、开放问题与默认值；必须见数据后才能定的事项

### 5.1 仍属栈层、带默认值的开放问题

1. 正式对外注册的 w3id 组织短码尚未确定。**默认**：继续使用 `https://w3id.org/poc-kb/`。注册后旧基址做 301/303，不改路径尾段。
2. 检索服务的知识库划分依部署而定。**默认**：对接契约按公开上游 WeKnora v0.9.0 的返回字段设计（知识库标识、文档标识、ContentRevision）；若返回字段不同，只改映射表，不改“三件套锚点”原则。
3. 生成的发布快照是否进 Git。**默认**：`release/snapshots/{version}/` 在打标签时提交；`gen/`、WIDOCO 整站、TDB2、扫描报告默认不进主干。
4. RDF 1.2 再化器是否用于语句级出处。**默认**：先输出 RDF 1.1 兼容 Turtle。若日后数据需要语句级出处且 Jena 6.3.0 在实际部署中表现稳定，再打开再化器；否则用独立的出处对象，不把再化器当成诊断事件模型。

### 5.2 只能见到数据之后才能定的事项

下列内容明确**等待数据**，本文件不给预制答案，也不把 v2.5 备份里的旧结论当作现行决定：

- 全部能力、类、属性、关系、枚举与字段表；
- 能力问题的具体条目与 SPARQL 查询内容；
- SHACL 形状的具体约束内容（除“由 LinkML 生成 + 必要时手写 extras”这一机制）；
- 首个业务切片选哪一个域、包含哪些对象；
- 模块如何按系统域拆分、HermiT 超时是否需要按模块调整；
- 任何质量评分、行动优先级、上行权重系数等业务数值；
- 业务流程字段哪些（若有）要进入本体，哪些永远留在应用库；
- 保守扩展的形式化证明（只有先出现核心模块与扩展模块之后才有对象可证）。

---

## 附录：版本核对来源

下列链接为 2026-11-24 用以核对版本的公开页面。收费标准全文仍未取得的，本文件只引用其作为对齐政策，不编造条款。

| 对象 | 来源 |
|---|---|
| LinkML 1.12.1 | https://github.com/linkml/linkml/releases ；https://pypi.org/project/linkml/ |
| Jena / Fuseki 6.3.0 | https://jena.apache.org/download/ ；CHANGES 载明 2026-11-22 发布，且 6.x 需 Java 21 |
| pySHACL 0.40.2 | https://github.com/RDFLib/pySHACL/releases |
| RDFLib 7.6.0 | https://github.com/RDFLib/rdflib/releases/tag/7.6.0 |
| ROBOT 1.9.11 | https://github.com/ontodev/robot/releases |
| WIDOCO 1.4.26 | https://github.com/dgarijo/Widoco/releases/tag/v1.4.26 |
| WeKnora v0.9.0 | https://github.com/Tencent/WeKnora/releases/tag/v0.9.0 |
| FOOPS! v0.4.0 | https://zenodo.org/records/20024871 |
| OOPS! | https://oops.linkeddata.es/ |
| OWL 2 Profiles | https://www.w3.org/TR/owl2-profiles/ |
| SHACL 推荐标准 | https://www.w3.org/TR/shacl/ （2017-07-20） |
| SHACL 1.2 仍为草案 | https://www.w3.org/TR/shacl12-core/ |
| BFO 2020 / ISO/IEC 21838-2:2021 | https://www.iso.org/standard/74572.html |
| Protégé 6.0.0-alpha-1 | https://github.com/protegeproject/protege-distribution/releases |

