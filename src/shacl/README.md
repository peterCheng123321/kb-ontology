# 手写补充 SHACL 形状说明（src/shacl/extras/）

依据 [docs/ONTOLOGY-TECH-STACK-v3.md](../../docs/ONTOLOGY-TECH-STACK-v3.md) §2.5，主体形状由 `make gen` 从 LinkML 自动生成至 `gen/shacl/poc-kb.shacl.ttl`；仅当 LinkML 生成器覆盖不到时才在本目录手写补充形状：

1. `privacy.shacl.ttl`：
   - **理由**：LinkML 无法表达全局跨所有类/谓词的隐私禁用规则。本文件使用 SHACL-SPARQL 检查全图任何字面量均不得匹配 17 位车辆识别号（VIN）正则 `^[A-HJ-NPR-Z0-9]{17}$`，且不得出现 `vin`、`vehicle_id`、`cdescr`、`narrative`、`dialogue` 类敏感谓词。
2. `stat-suppression.shacl.ttl`：
   - **理由**：LinkML 无法表达跨槽位条件互斥约束（当 `insp:suppressed = true` 时不得携带 `insp:defectCount`；当 `insp:suppressed = false` 时 `insp:defectCount` 必须存在且 `>= 5`）。
3. `candidate-link.shacl.ttl`：
   - **理由**：LinkML `gen-owl` 对数值边界 facet 存在与 HermiT 的 datatype 兼容问题（已实测 v1 `xsd:float` + `xsd:double` facet 报错）。因此把 `core:score` 的 `xsd:decimal` ∈ `[0.0, 1.0]` 范围约束移入本 SHACL 文件，同时保证 OWL 2 DL / HermiT 零报错与 ABox 严格校验。
