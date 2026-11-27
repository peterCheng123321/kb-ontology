# 手写补充 SHACL 形状说明（src/shacl/extras/）

依据 [docs/ONTOLOGY-TECH-STACK-v3.md](../../docs/ONTOLOGY-TECH-STACK-v3.md) §2.5，主体形状在测试进程内从 LinkML 生成；`make gen` 仍把同一结果写到已忽略的 `gen/shacl/poc-kb.shacl.ttl`。仅当 LinkML 生成器覆盖不到时才在本目录手写补充形状：

1. `privacy.shacl.ttl`：
   - **理由**：LinkML 无法表达跨类、跨谓词的隐私禁用规则。形状用 `sh:targetSubjectsOf rdf:type` 覆盖每一个有类型的节点（没有 `rdf:type` 的节点不在目标内）。字面量用 XPath `REGEX`（没有词边界元字符）和 `"i"` 标志，模式为 `(^|[^A-Za-z0-9])[A-HJ-NPR-Z0-9]{17}([^A-Za-z0-9]|$)`，因此嵌入文本与大小写混排都会命中；并拒绝以 `vin`、`vehicle_id`、`cdescr`、`narrative`、`dialogue` 结尾的敏感谓词。
2. `stat-suppression.shacl.ttl`：
   - **理由**：LinkML 无法表达跨槽位条件互斥约束（当 `insp:suppressed = true` 时不得携带 `insp:defectCount`；当 `insp:suppressed = false` 时 `insp:defectCount` 必须存在且 `>= 5`）。
3. `candidate-link.shacl.ttl`：
   - **理由**：LinkML `gen-owl` 对数值边界 facet 存在与 HermiT 的 datatype 兼容问题（已实测 v1 `xsd:float` + `xsd:double` facet 报错）。因此把 `core:score` 的 `xsd:decimal` ∈ `[0.0, 1.0]` 范围约束移入本 SHACL 文件，同时保证 OWL 2 DL / HermiT 零报错与 ABox 严格校验。
