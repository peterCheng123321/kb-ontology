# 手写补充 SHACL 形状说明（src/shacl/extras/）

依据 [docs/ONTOLOGY-TECH-STACK-v3.md](../../docs/ONTOLOGY-TECH-STACK-v3.md) §2.5，主体形状在测试进程内从 LinkML 生成；`make gen` 仍把同一结果写到已忽略的 `gen/`。仅当生成器覆盖不到时才手写补充形状：

1. `privacy.shacl.ttl`：`sh:SPARQLTarget` 选取每一个三元组的主体，因此有类型节点、无类型 IRI 和空白节点上的字面量都会检查。XPath `REGEX` 没有词边界元字符，故用 `(^|[^A-Za-z0-9])[A-HJ-NPR-Z0-9]{17}([^A-Za-z0-9]|$)` 与 `"i"` 标志，嵌入文本和大小写混排都会命中；并拒绝以 `vin`、`vehicle_id`、`cdescr`、`narrative`、`dialogue` 结尾的敏感谓词。主体 IRI 本身不在检查范围内。
2. `stat-suppression.shacl.ttl`：`insp:suppressed = true` 时不得带 `insp:defectCount`；`suppressed = false` 时 `defectCount` 必须存在且 `>= 5`。
3. `candidate-link.shacl.ttl`：`core:score` 的 `xsd:decimal` 范围 `[0.0, 1.0]` 放在 SHACL，避开 OWL 数值边界与推理器的类型冲突。
