# 跨源对齐与上层本体政策（POC v3.0-exp）

依据 [docs/ONTOLOGY-TECH-STACK-v3.md](../../docs/ONTOLOGY-TECH-STACK-v3.md) §2.11：

1. **允许的对齐谓词**：仅使用 `skos:exactMatch`（同语义范畴）、`skos:closeMatch`（覆盖范围存在宽窄差异的近似对齐）与 `rdfs:seeAlso`（仅供人参考）。未经数据实证，不得随意使用 `owl:equivalentClass`。
2. **不复制收费标准**：对 SAE J2012 / ISO 15031-6、ISO 14229、GB/T 32960、JT/T 1132.3 等标准仅作 IRI 引用或字段槽位推导，不复制收费文本或整份词表。
3. **上层本体（BFO 2020）**：仅在 LinkML `annotations.bfo_alignment` 中记录 BFO 2020 范畴对应关系（例如 `Component` → `BFO_0000024`/`BFO_0000030`，`Complaint`/`InspectionDefectStat` → `BFO_0000031`，`BatterySnippetSummary` → `BFO_0000015` 观测摘要与 `sosa:Observation`），**运行时不导入完整 BFO 公理集**。
4. **硬键 vs 候选边**：跨源硬键仅限官方等值主键（如 `CAMPNO`、完全一致的跨国厂内召回号词元、`dtc_code -> fix_id -> part_id`）；其余基于 MMY、系统映射、时间窗、词表、J2012 子系统段的跨源关联一律物化为 `core:CandidateLink`，强制携带 `method`、`score`（`xsd:decimal` ∈ [0,1]）和 `reviewStatus`。
