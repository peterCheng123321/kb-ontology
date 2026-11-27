PY ?= .venv/bin/python
GEN_OWL ?= .venv/bin/gen-owl
GEN_SHACL ?= .venv/bin/gen-shacl
GEN_JSONLD ?= .venv/bin/gen-jsonld-context
GEN_JSONSCHEMA ?= .venv/bin/gen-json-schema
SCHEMA = src/linkml/catalog.yaml
.PHONY: help gen test
help:
	@echo "Targets: gen | test"
gen:
	mkdir -p gen/owl gen/shacl gen/jsonld gen/jsonschema
	$(GEN_OWL) --no-metaclasses --no-type-objects $(SCHEMA) > gen/owl/poc-kb.owl.ttl
	$(GEN_SHACL) --non-closed $(SCHEMA) > gen/shacl/poc-kb.shacl.ttl
	$(GEN_JSONLD) $(SCHEMA) > gen/jsonld/poc-kb.context.jsonld
	$(GEN_JSONSCHEMA) $(SCHEMA) > gen/jsonschema/poc-kb.schema.json
test:
	@if [ ! -x "$(PY)" ]; then echo "找不到 Python 解释器：$(PY)（可用 PY= 覆盖）" >&2; exit 1; fi
	$(PY) -m pytest -q
