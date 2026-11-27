PY ?= .venv/bin/python
GEN_OWL ?= .venv/bin/gen-owl
GEN_SHACL ?= .venv/bin/gen-shacl
GEN_JSONLD ?= .venv/bin/gen-jsonld-context
GEN_JSONSCHEMA ?= .venv/bin/gen-json-schema
SCHEMA = src/linkml/catalog.yaml

.PHONY: help gen slice baseline build validate robot query all

help:
	@echo "Targets: gen | slice | baseline | build | validate | robot | query | all"

gen:
	mkdir -p gen/owl gen/shacl gen/jsonld gen/jsonschema
	$(GEN_OWL) --no-metaclasses --no-type-objects $(SCHEMA) > gen/owl/poc-kb.owl.ttl
	$(GEN_SHACL) --non-closed $(SCHEMA) > gen/shacl/poc-kb.shacl.ttl
	$(GEN_JSONLD) $(SCHEMA) > gen/jsonld/poc-kb.context.jsonld
	$(GEN_JSONSCHEMA) $(SCHEMA) > gen/jsonschema/poc-kb.schema.json

slice:
	$(PY) scripts/build_slice_honda_2018.py

baseline: slice
	$(PY) scripts/baseline_regression.py

build: gen
	$(PY) scripts/v3_build_graph.py

validate:
	$(PY) scripts/v3_validate.py
	$(PY) -m pytest tests -q

robot:
	bash ci/robot.sh

query:
	$(PY) scripts/v3_run_cq.py

all: baseline build validate robot query
