#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ -n "${JAVA_BIN:-}" ]; then
  JAVA="$JAVA_BIN"
elif [ -x "/opt/homebrew/opt/openjdk@21/bin/java" ]; then
  JAVA="/opt/homebrew/opt/openjdk@21/bin/java"
elif [ -x "/opt/homebrew/opt/openjdk/bin/java" ]; then
  JAVA="/opt/homebrew/opt/openjdk/bin/java"
else
  JAVA="java"
fi

ROBOT_JAR="${ROBOT_JAR:-tools/robot.jar}"
if [ ! -f "$ROBOT_JAR" ]; then
  echo "ERROR: $ROBOT_JAR not found. Download ROBOT 1.9.11 first." >&2
  exit 1
fi

OUT_DIR="gen/robot"
mkdir -p "$OUT_DIR"

echo "=== Java & ROBOT version ==="
"$JAVA" -version 2>&1 | head -n 3
"$JAVA" -jar "$ROBOT_JAR" --version

echo "=== 1. Merge LinkML OWL + OWL 2 DL annotation/alignment supplement ==="
"$JAVA" -Xmx4g -jar "$ROBOT_JAR" merge \
  --input gen/owl/poc-kb.owl.ttl \
  --input src/linkml/owl_annotations.ttl \
  annotate \
  --ontology-iri "https://w3id.org/poc-kb/catalog" \
  --version-iri "https://w3id.org/poc-kb/catalog/3.0.0-exp" \
  --annotation "http://purl.org/dc/elements/1.1/description" "Data-first modular LinkML ontology for multi-source automotive after-sales knowledge base experiments (POC v3.0-exp)." \
  --annotation "http://purl.org/dc/terms/title" "Automotive After-Sales Knowledge Base Ontology (Modular v3.0-exp)" \
  --annotation "http://www.w3.org/2002/07/owl#versionInfo" "3.0.0-exp" \
  --output "$OUT_DIR/merged-tbox.ttl"

echo "=== 2. Validate OWL 2 DL profile (blocking gate) ==="
"$JAVA" -Xmx4g -jar "$ROBOT_JAR" validate-profile \
  --profile DL \
  --input "$OUT_DIR/merged-tbox.ttl" \
  --output "$OUT_DIR/dl-profile.txt"
cat "$OUT_DIR/dl-profile.txt"

echo "=== 3. Validate OWL 2 RL profile (informational, non-blocking) ==="
set +e
"$JAVA" -Xmx4g -jar "$ROBOT_JAR" validate-profile \
  --profile RL \
  --input "$OUT_DIR/merged-tbox.ttl" \
  --output "$OUT_DIR/rl-profile.txt"
RL_RC=$?
set -e
echo "RL exit code: $RL_RC (recorded in $OUT_DIR/rl-profile.txt)"
head -n 25 "$OUT_DIR/rl-profile.txt" || true

echo "=== 4. HermiT consistency & classification on TBox ==="
"$JAVA" -Xmx4g -jar "$ROBOT_JAR" reason \
  --reasoner hermit \
  --input "$OUT_DIR/merged-tbox.ttl" \
  --output "$OUT_DIR/reasoned-tbox.owl"

if [ -f "rdf/v3/sample_abox.ttl" ]; then
  echo "=== 4b. HermiT consistency check on TBox + sample ABox ==="
  "$JAVA" -Xmx4g -jar "$ROBOT_JAR" merge \
    --input "$OUT_DIR/merged-tbox.ttl" \
    --input "rdf/v3/sample_abox.ttl" \
    --output "$OUT_DIR/merged-sample.ttl"
  "$JAVA" -Xmx4g -jar "$ROBOT_JAR" reason \
    --reasoner hermit \
    --input "$OUT_DIR/merged-sample.ttl" \
    --output "$OUT_DIR/reasoned-sample.owl"
fi

echo "=== 5. ROBOT quality report ==="
set +e
"$JAVA" -Xmx4g -jar "$ROBOT_JAR" report \
  --input "$OUT_DIR/merged-tbox.ttl" \
  --fail-on none \
  --output "$OUT_DIR/report.tsv"
set -e
head -n 30 "$OUT_DIR/report.tsv" || true

echo "=== ROBOT pipeline completed ==="
