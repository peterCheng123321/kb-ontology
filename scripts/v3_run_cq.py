#!/usr/bin/env python3
"""Run CQ1-CQ7 SPARQL competency questions, assert all acceptance criteria, and render figures.

Loads all 6 modular v3 ABox TTLs (rdf/v3/*.ttl) into pyoxigraph (SPARQL 1.1 compliant,
sub-second execution on 721k+ triples), executes src/sparql/CQ1..CQ7.rq, cross-checks
suppressed MOT cells do not leak counts, writes docs/stats/v3-cq-results.json, and renders:
  - figs/v3_chain_odino_11407338.png (6-source closed-loop showcase chain)
  - figs/v3_module_overview.png (modular v3 ABox nodes, edges, and triples overview)
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import networkx as nx
from pyoxigraph import RdfFormat, Store

REPO_ROOT = Path(__file__).resolve().parents[1]
RDF_V3 = REPO_ROOT / "rdf" / "v3"
SPARQL_DIR = REPO_ROOT / "src" / "sparql"
STATS_DIR = REPO_ROOT / "docs" / "stats"
FIGS_DIR = REPO_ROOT / "figs"
FIGS_DIR.mkdir(parents=True, exist_ok=True)

MODULES = ("core", "recall", "diagnostics", "inspection", "signal", "ev_battery")


def term_to_str(val: Any) -> str:
    if val is None:
        return ""
    # pyoxigraph Literal / NamedNode
    if hasattr(val, "value"):
        return str(val.value)[:400]
    return str(val)[:400]


def run_sparql(store: Store, query_text: str) -> list[dict[str, str]]:
    res = store.query(query_text)
    vars_ = [v.value for v in res.variables]
    rows = []
    for sol in res:
        rec = {}
        for v in vars_:
            rec[v] = term_to_str(sol[v])
        rows.append(rec)
    return rows


def check_assertions(results: dict[str, dict], store: Store) -> list[dict]:
    checks = []

    def rec(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    # CQ1: Non-empty, hard_key == 0, hits TC 2020236 / 2023679 / 2024262
    q1 = results["CQ1_cross_jurisdiction_recall"]["rows"]
    q1_hard = [r for r in q1 if r.get("linkKind") == "hard"]
    q1_ca_ids = {r.get("caId") for r in q1}
    fuel_hits = sorted(q1_ca_ids & {"2020236", "2023679", "2024262"})
    rec("CQ1_non_empty", len(q1) > 0, f"n={len(q1)}")
    rec("CQ1_hard_key_zero_matches_stats", len(q1_hard) == 0, f"hard_rows={len(q1_hard)}")
    rec("CQ1_fuel_pump_ca_match", len(fuel_hits) >= 1, f"matched_fuel_ca={fuel_hits}")
    rec(
        "CQ1_candidates_have_provenance",
        all(r.get("method") and r.get("score") and r.get("reviewStatus") for r in q1),
        "all rows carry method/score/reviewStatus",
    )

    # CQ2: P1326 shows VOLKSWAGEN + mismatch=true; C1391 & C2200 marked UNCOVERED
    q2 = results["CQ2_dtc_make_context_disambiguation"]["rows"]
    p1326 = [r for r in q2 if r.get("code") == "P1326"]
    c1391 = [r for r in q2 if r.get("code") == "C1391"]
    c2200 = [r for r in q2 if r.get("code") == "C2200"]
    rec(
        "CQ2_P1326_vw_mismatch",
        any(r.get("makeContext") == "VOLKSWAGEN" and r.get("mismatch") == "true" for r in p1326),
        f"P1326 rows={p1326}",
    )
    rec(
        "CQ2_C1391_C2200_uncovered",
        any(r.get("makeContext") == "UNCOVERED" for r in c1391) and any(r.get("makeContext") == "UNCOVERED" for r in c2200),
        f"C1391={len(c1391)}, C2200={len(c2200)}",
    )

    # CQ3: >= 1 NHTSA head hits non-suppressed MOT stat; suppressed cells never emit defectCount
    q3 = results["CQ3_component_to_mot_defect_stats"]["rows"]
    q3_heads = sorted({r.get("nhtsaHead") for r in q3 if r.get("nhtsaHead")})
    leak_rows = run_sparql(
        store,
        """
        PREFIX insp: <https://w3id.org/poc-kb/insp/>
        SELECT ?s ?cnt WHERE { ?s insp:suppressed true ; insp:defectCount ?cnt . }
        """,
    )
    min_cnt = min((int(r["defectCount"]) for r in q3 if r.get("defectCount", "").isdigit()), default=0)
    rec("CQ3_nhtsa_to_mot_visible", len(q3) > 0 and len(q3_heads) >= 1, f"rows={len(q3)}, heads={q3_heads}")
    rec("CQ3_suppressed_zero_leak", len(leak_rows) == 0 and min_cnt >= 5, f"leak_rows={len(leak_rows)}, min_visible_cnt={min_cnt}")

    # CQ4: All 3 target heads return >= 1 Honda CAN message & VSSo closeMatch exists
    q4 = results["CQ4_component_to_can_vss"]["rows"]
    q4_heads = {r.get("head") for r in q4}
    target_heads = {"FORWARD COLLISION AVOIDANCE", "STEERING", "SERVICE BRAKES"}
    vsso_hits = [r for r in q4 if r.get("vssoClass")]
    rec("CQ4_all_three_heads_covered", target_heads.issubset(q4_heads), f"covered={sorted(q4_heads)}")
    rec("CQ4_vsso_alignment_present", len(vsso_hits) > 0, f"vsso_aligned_rows={len(vsso_hits)}")

    # CQ5: P0300 & P0172 return PIDs with unit/formula & dtc_pid_subsystem
    q5 = results["CQ5_dtc_to_obd_pid_vss"]["rows"]
    q5_codes = {r.get("code") for r in q5}
    q5_with_formula = [r for r in q5 if r.get("formula")]
    q5_with_vss = [r for r in q5 if r.get("vssPath")]
    rec("CQ5_both_dtcs_mapped", {"P0300", "P0172"}.issubset(q5_codes), f"codes={sorted(q5_codes)}, rows={len(q5)}")
    rec("CQ5_formula_and_vss_present", len(q5_with_formula) > 0 and len(q5_with_vss) > 0, f"formula={len(q5_with_formula)}, vss={len(q5_with_vss)}")

    # CQ6: EV battery fault summary covers all 3 brand cohorts & fault_abnormal + normal, aligned to TractionBattery
    q6 = results["CQ6_ev_battery_fault_summary_vss"]["rows"]
    q6_brands = {r.get("brandCohort") for r in q6}
    q6_labels = {r.get("faultLabel") for r in q6}
    total_snips = sum(int(r["totalSnippets"]) for r in q6 if r.get("totalSnippets", "").isdigit())
    rec("CQ6_three_brands_and_labels", len(q6_brands) == 3 and {"normal", "fault_abnormal"}.issubset(q6_labels), f"brands={sorted(q6_brands)}, labels={sorted(q6_labels)}")
    rec("CQ6_snippets_and_vss_aligned", total_snips == 700582 and all(int(r.get("alignedVssSignals", 0)) >= 5 for r in q6), f"total_snippets={total_snips}")

    # CQ7: All 4 hopKinds present for ODINO 11407338
    q7 = results["CQ7_multisource_closed_loop_chain"]["rows"]
    q7_hops = sorted({r.get("hopKind") for r in q7})
    expected_hops = {"1_recall_us_ca", "2_dtc_repair_part", "3_uk_mot_stat", "4_can_vss_signal"}
    rec("CQ7_all_four_multisource_hops", expected_hops.issubset(set(q7_hops)), f"hops={q7_hops}, rows={len(q7)}")

    return checks


def plot_cq7_chain(q7_rows: list[dict[str, str]]) -> Path:
    """Render 6-source closed-loop showcase graph around Honda CR-V 2018 complaint 11407338."""
    G = nx.DiGraph()

    def addn(nid: str, label: str, kind: str) -> None:
        G.add_node(nid, label=label, kind=kind)

    addn("veh", "VehicleModelYear\nHONDA CR-V 2018", "vehicle")
    addn("cmpl", "Complaint\nODINO 11407338\n(NHTSA)", "complaint")
    G.add_edge("cmpl", "veh", label="vehicle", style="hard")

    def ensure_comp(head_name: str) -> str:
        cid = f"comp:{head_name}"
        if cid not in G:
            short = head_name.replace("FORWARD COLLISION AVOIDANCE", "FORWARD COLLISION\nAVOIDANCE")
            addn(cid, f"Component\n{short}", "component")
            G.add_edge("cmpl", cid, label="hasComponent", style="hard")
        return cid

    fuel_comp = ensure_comp("FUEL SYSTEM")

    # Branch 1: US -> CA Recall
    us_seen = set()
    for r in q7_rows:
        if r["hopKind"] != "1_recall_us_ca":
            continue
        us_id = r["sourceEntity"]
        ca_id = r["targetEntity"]
        if us_id not in us_seen:
            addn(us_id, f"Recall {us_id}\n(NHTSA US)", "recall_us")
            G.add_edge("cmpl", us_id, label=f"mmy_comp\n{r['score']}", style="candidate")
            G.add_edge(us_id, fuel_comp, label="hasComponent", style="hard")
            us_seen.add(us_id)
        if ca_id.startswith("CA:"):
            addn(ca_id, f"Recall {ca_id}\n(TC VRDB)", "recall_ca")
            G.add_edge(us_id, ca_id, label=f"xjur {r['detail'].replace('xjur_score=', '')}", style="candidate")

    # Branch 2: DTC -> RepairStep -> Part (pick top 2 codes with repair steps + 1 without)
    dtc_added = 0
    step_added = 0
    for r in q7_rows:
        if r["hopKind"] != "2_dtc_repair_part":
            continue
        code = r["sourceEntity"]
        did = f"dtc:{code}"
        if did not in G and dtc_added < 3:
            addn(did, f"DTC {code}\n(Multi-OEM)", "dtc")
            G.add_edge("cmpl", did, label="mentionsDtc", style="candidate")
            dtc_added += 1
        if did in G and r["targetEntity"] != "no_mechanic_sample" and step_added < 2:
            sid = f"step:{step_added}"
            pid = f"part:{step_added}"
            t_short = r["detail"][:26] + ("..." if len(r["detail"]) > 26 else "")
            p_short = r["targetEntity"][:24] + ("..." if len(r["targetEntity"]) > 24 else "")
            addn(sid, f"RepairStep\n{t_short}", "step")
            addn(pid, f"Part\n{p_short}", "part")
            G.add_edge(did, sid, label="forDtc (hard)", style="hard")
            G.add_edge(sid, pid, label="usesPart (hard)", style="hard")
            step_added += 1

    # Branch 3: UK MOT 2023 CR-V 2018 aggregated stats (attach to true sourceEntity component!)
    mot_added = 0
    for r in q7_rows:
        if r["hopKind"] != "3_uk_mot_stat" or mot_added >= 2:
            continue
        src_comp = ensure_comp(r["sourceEntity"])
        mid = f"mot:{mot_added}"
        cnt_part = r["detail"].split("|")[0].strip()
        addn(mid, f"UK MOT 2023\n{r['targetEntity']}\n{cnt_part} (k>=5)", "mot")
        G.add_edge(src_comp, mid, label="SKOS MOT", style="skos")
        mot_added += 1

    # Branch 4: Honda CAN message -> VSS (attach to true sourceEntity component!)
    can_added = 0
    seen_can_pairs = set()
    for r in q7_rows:
        if r["hopKind"] != "4_can_vss_signal" or can_added >= 2:
            continue
        pair = (r["sourceEntity"], r["targetEntity"])
        if pair in seen_can_pairs:
            continue
        seen_can_pairs.add(pair)
        src_comp = ensure_comp(r["sourceEntity"])
        cid = f"can:{r['targetEntity']}"
        if cid not in G:
            addn(cid, f"Honda CAN\n{r['targetEntity']}\n(opendbc)", "can")
            G.add_edge(src_comp, cid, label=f"can {r['score']}", style="candidate")
        vid = f"vss:{r['detail']}"
        if vid not in G and r["detail"].startswith("Vehicle."):
            v_short = r["detail"].replace("Vehicle.", "").replace(".", ".\n")
            addn(vid, f"VSS v6.1\n{v_short}", "vss")
            G.add_edge(cid, vid, label="mapsToVss", style="skos")
        can_added += 1

    # Deterministic layered layout
    col_map = {
        "vehicle": 0, "complaint": 0,
        "component": 1, "dtc": 1,
        "recall_us": 2, "step": 2, "mot": 2, "can": 2,
        "recall_ca": 3, "part": 3, "vss": 3,
    }
    by_col = defaultdict(list)
    for n, d in G.nodes(data=True):
        by_col[col_map.get(d["kind"], 2)].append(n)
    pos = {}
    for col, nodes in by_col.items():
        for i, n in enumerate(nodes):
            y = (len(nodes) - 1) / 2.0 - i * 1.25
            pos[n] = (col * 2.6, y)

    palette = {
        "vehicle": "#4C78A8",
        "complaint": "#F58518",
        "component": "#54A24B",
        "recall_us": "#E45756",
        "recall_ca": "#D67195",
        "dtc": "#72B7B2",
        "step": "#EECA3B",
        "part": "#9D755D",
        "mot": "#B279A2",
        "can": "#88D27A",
        "vss": "#59A14F",
    }

    plt.figure(figsize=(18, 10.5), dpi=150)
    ax = plt.gca()
    ax.set_title(
        "Ontology v3 Six-Source Closed-Loop Chain (Honda CR-V 2018, ODINO 11407338)\n"
        "Solid dark = Hard Key | Orange dashed = CandidateLink | Blue dotted = SKOS / VSS Alignment",
        fontsize=12,
        pad=16,
    )
    nx.draw_networkx_nodes(
        G, pos,
        node_color=[palette.get(G.nodes[n]["kind"], "#ccc") for n in G.nodes],
        node_size=4200, linewidths=0.9, edgecolors="#222", ax=ax,
    )
    nx.draw_networkx_labels(
        G, pos,
        labels={n: G.nodes[n]["label"] for n in G.nodes},
        font_size=6.5, ax=ax,
    )
    for style, color, ls, width in (
        ("hard", "#222222", "solid", 1.8),
        ("candidate", "#E67E22", "dashed", 1.4),
        ("skos", "#2980B9", "dotted", 1.6),
    ):
        el = [(u, v) for u, v, d in G.edges(data=True) if d.get("style") == style]
        if el:
            nx.draw_networkx_edges(
                G, pos, edgelist=el, width=width, edge_color=color, style=ls,
                arrows=True, arrowsize=14, ax=ax, connectionstyle="arc3,rad=0.06",
            )
    elabs = {(u, v): d.get("label", "") for u, v, d in G.edges(data=True)}
    nx.draw_networkx_edge_labels(G, pos, edge_labels=elabs, font_size=6.0, ax=ax, label_pos=0.48)

    patches = [
        mpatches.Patch(color=palette[k], label=k)
        for k in palette
        if any(G.nodes[n]["kind"] == k for n in G.nodes)
    ]
    ax.legend(handles=patches, loc="lower left", ncol=3, fontsize=7.5, framealpha=0.92)
    ax.axis("off")
    plt.tight_layout()
    out_png = FIGS_DIR / "v3_chain_odino_11407338.png"
    plt.savefig(out_png, bbox_inches="tight", facecolor="white")
    plt.close()
    return out_png


def plot_module_overview() -> Path:
    """Render modular v3 ABox scale overview (triples per module + candidate edge families)."""
    gstats = json.loads((STATS_DIR / "v3-graph-stats.json").read_text(encoding="utf-8"))
    mods = gstats["modules"]
    cands = {k: v for k, v in gstats["candidate_edges"].items() if k != "candidate_total"}

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6), dpi=150)

    m_names = list(mods.keys())
    m_triples = [mods[m]["triples"] for m in m_names]
    bars1 = ax1.barh(m_names[::-1], m_triples[::-1], color="#4C78A8")
    ax1.set_xscale("log")
    ax1.set_xlabel("ABox Triples (log scale)")
    ax1.set_title(f"Modular LinkML v3 ABox Scale (Total: {gstats['total_abox_triples']:,} triples)")
    for b in bars1:
        w = b.get_width()
        ax1.text(w * 1.12, b.get_y() + b.get_height() / 2, f"{int(w):,}", va="center", fontsize=8)
    ax1.set_xlim(right=max(m_triples) * 4.5)

    c_items = sorted(cands.items(), key=lambda kv: kv[1])
    c_names = [k for k, _ in c_items]
    c_vals = [v for _, v in c_items]
    colors2 = ["#E45756" if k in {"xjur_mmy_system_window", "dtc_make_context", "dtc_pid_subsystem", "component_mot_group", "component_can_message", "battery_fault_signal"} else "#999999" for k in c_names]
    bars2 = ax2.barh(c_names, c_vals, color=colors2)
    ax2.set_xscale("log")
    ax2.set_xlabel("CandidateLink Count (log scale)")
    ax2.set_title("CandidateLink Families (Red = New v3 Cross-Source | Gray = Phase 1 Baseline)")
    for b in bars2:
        w = b.get_width()
        ax2.text(w * 1.12, b.get_y() + b.get_height() / 2, f"{int(w):,}", va="center", fontsize=8)
    ax2.set_xlim(right=max(c_vals) * 4.5)

    plt.tight_layout()
    out_png = FIGS_DIR / "v3_module_overview.png"
    plt.savefig(out_png, bbox_inches="tight", facecolor="white")
    plt.close()
    return out_png


def main() -> int:
    t0 = time.time()
    store = Store()
    for mod in MODULES:
        p = RDF_V3 / f"{mod}.ttl"
        if not p.exists():
            print(f"ERROR: missing {p}; run `make build` first.", file=sys.stderr)
            return 1
        store.load(path=str(p), format=RdfFormat.TURTLE)
    load_sec = round(time.time() - t0, 2)
    print(f"Loaded {len(store):,} triples into pyoxigraph in {load_sec}s")

    results: dict[str, dict] = {}
    for rq in sorted(SPARQL_DIR.glob("CQ*.rq")):
        t1 = time.time()
        rows = run_sparql(store, rq.read_text(encoding="utf-8"))
        sec = round(time.time() - t1, 4)
        results[rq.stem] = {"n": len(rows), "seconds": sec, "rows": rows}
        print(f"  {rq.stem}: n={len(rows)} ({sec}s)")

    checks = check_assertions(results, store)
    all_passed = all(c["passed"] for c in checks)

    png_chain = plot_cq7_chain(results["CQ7_multisource_closed_loop_chain"]["rows"])
    png_overview = plot_module_overview()

    out = {
        "measured_at": "2026-11-25 Asia/Shanghai",
        "engine": "pyoxigraph (SPARQL 1.1)",
        "store_triples": len(store),
        "load_seconds": load_sec,
        "all_assertions_passed": all_passed,
        "assertions": checks,
        "figures": [str(png_chain.relative_to(REPO_ROOT)), str(png_overview.relative_to(REPO_ROOT))],
        "queries": results,
    }
    out_path = STATS_DIR / "v3-cq-results.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path} | all_assertions_passed={all_passed}")
    print(f"Rendered figures: {png_chain.name}, {png_overview.name}")
    for c in checks:
        status = "PASS" if c["passed"] else "FAIL"
        print(f"  [{status}] {c['check']}: {c['detail']}")
    return 0 if all_passed else 2


if __name__ == "__main__":
    sys.exit(main())
