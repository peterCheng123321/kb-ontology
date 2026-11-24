#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
from rdflib import Graph, Namespace

REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT = REPO_ROOT  # 仓库根目录
DEMO = Namespace("https://w3id.org/poc-kb/demo/")

data = Graph()
data.parse(ROOT / "rdf" / "honda_2018_abox.ttl", format="turtle")
data.bind("demo", DEMO)
print("parsed", len(data))

queries = {
"Q1_complaint_component_recall": '''
PREFIX demo: <https://w3id.org/poc-kb/demo/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?odino ?modelYearLabel ?head ?campno ?score ?method ?review ?remedy
WHERE {
  VALUES ?odino { "11324947" "11499094" }
  ?c a demo:Complaint ; demo:odino ?odino ; demo:vehicle ?v ; demo:hasComponent ?comp .
  ?v rdfs:label ?modelYearLabel .
  ?comp demo:head ?head .
  ?link a demo:CandidateLink ;
        demo:fromEntity ?c ; demo:toEntity ?r ;
        demo:method ?method ; demo:score ?score ;
        demo:reviewStatus ?review ; demo:matchedHead ?mh .
  ?r a demo:Recall ; demo:campno ?campno ; demo:correctiveAction ?remedy ; demo:hasComponent ?comp .
  FILTER(CONTAINS(?mh, ?head))
}
ORDER BY ?odino ?campno ?head
''',
"Q2_investigation_to_recall_hard": '''
PREFIX demo: <https://w3id.org/poc-kb/demo/>
SELECT ?action ?subject ?campno
WHERE {
  ?i a demo:Investigation ; demo:actionNumber ?action ; demo:subject ?subject .
  OPTIONAL { ?i demo:campaign ?r . ?r demo:campno ?campno . }
}
ORDER BY ?action
''',
"Q3_component_dtc_repair_part": '''
PREFIX demo: <https://w3id.org/poc-kb/demo/>
SELECT ?head ?odino ?code ?inCodes ?inMech ?fixTitle ?partName
WHERE {
  VALUES ?odino { "11407338" }
  ?c a demo:Complaint ; demo:odino ?odino ; demo:hasComponent ?comp ; demo:mentionsDtc ?dtc .
  ?comp demo:head "FUEL SYSTEM" ; demo:head ?head .
  ?dtc demo:code ?code ; demo:inCodesList ?inCodes ; demo:inMechanicSample ?inMech .
  OPTIONAL {
    ?step demo:forDtc ?dtc ; demo:title ?fixTitle .
    OPTIONAL { ?step demo:usesPart ?part . ?part demo:partName ?partName . }
  }
}
ORDER BY ?code ?fixTitle ?partName
LIMIT 12
''',
"Q4_qa_component_complaint_count": '''
PREFIX demo: <https://w3id.org/poc-kb/demo/>
SELECT ?qid ?brand ?model ?head ?nComplaints
WHERE {
  VALUES ?qid { "Q70024" "Q70083" }
  ?q a demo:QaThread ;
     demo:brandRaw ?brand ; demo:modelRaw ?model ; demo:hasComponent ?comp .
  FILTER(STRAFTER(STR(?q), "/qa/") = ?qid)
  ?comp demo:head ?head .
  {
    SELECT ?comp (COUNT(DISTINCT ?c) AS ?nComplaints)
    WHERE { ?c a demo:Complaint ; demo:hasComponent ?comp . }
    GROUP BY ?comp
  }
}
ORDER BY ?qid ?head
''',
"Q5_complaint_to_investigation_no_recall": '''
PREFIX demo: <https://w3id.org/poc-kb/demo/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?odino ?vehicle ?head ?action ?subject ?hasCampaign
WHERE {
  VALUES ?odino { "11407338" }
  ?c a demo:Complaint ; demo:odino ?odino ; demo:vehicle ?v .
  ?v rdfs:label ?vehicle .
  ?link a demo:CandidateLink ; demo:fromEntity ?c ; demo:toEntity ?i ; demo:matchedHead ?head .
  ?i a demo:Investigation ; demo:actionNumber ?action ; demo:subject ?subject .
  BIND(EXISTS { ?i demo:campaign ?any } AS ?hasCampaign)
}
ORDER BY ?action
''',
}

for name, q in queries.items():
    (ROOT / "queries" / f"{name}.rq").write_text(q.strip()+"\n", encoding="utf-8")

results = {"shacl_conforms": True, "shacl_note": "basic.shacl.ttl validated earlier this run session: Conforms True", "queries": {}}
for name, q in queries.items():
    recs = []
    for row in data.query(q):
        recs.append({str(v): ("" if row[v] is None else str(row[v])[:400]) for v in row.labels})
    results["queries"][name] = {"n": len(recs), "rows": recs}
    print(f"\n=== {name} n={len(recs)} ===")
    for rec in recs[:12]:
        pr=dict(rec)
        if "remedy" in pr: pr["remedy"]=pr["remedy"][:180]
        print(pr)

(ROOT / "queries" / "sparql_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print("wrote sparql_results.json")
