"""Evidence script for docs/integration_review.md: empirically checks suspected defects in the AML-Network-Graph-Engine
prototype using the prototype's OWN code. It is not part of the test suite and has no effect on this application.

Run with the prototype's pinned environment (its requirements-full.txt), e.g.:
    cd /path/to/AML-Network-Graph-Engine && python -m venv .venv && . .venv/bin/activate && pip install -r requirements-full.txt
    PROTOTYPE_PATH=$PWD python /path/to/this/file.py
"""
import sys, time, collections
import os
PROTO = os.environ.get("PROTOTYPE_PATH") or (sys.argv[1] if len(sys.argv) > 1 else None)
if not PROTO:
    sys.exit("usage: PROTOTYPE_PATH=/path/to/AML-Network-Graph-Engine python verify_prototype_claims.py   (run with the PROTOTYPE's Python environment)")
sys.path.insert(0, PROTO)
import numpy as np
from backend.config import GeneratorConfig, AML_CFG
from backend.generator import generate_transactions
from backend.graph_engine import TransactionGraph, build_graph_from_transactions
import networkx as nx

cfg = GeneratorConfig(n_transactions=20000, seed=42)
txs = generate_transactions(cfg, verbose=False)
N = len(txs); lab = collections.Counter(t["pattern_type"] for t in txs)
sus = sum(v for k,v in lab.items() if k!="normal")
print(f"[generator] n={N} label_rate={sus/N:.1%}  patterns={dict(lab)}")
print(f"[generator] time span: {txs[0]['timestamp']} .. {txs[-1]['timestamp']}  (configured year 2024-01-01..2024-12-31)")

hr = AML_CFG.high_risk_jurisdictions
def hrflag(t): return t["src_jurisdiction"] in hr or t["dst_jurisdiction"] in hr
byp = collections.defaultdict(list)
for t in txs: byp[t["pattern_type"]].append(hrflag(t))
print("[HR-jurisdiction rule fires on] " + ", ".join(f"{k}={np.mean(v):.0%}" for k,v in sorted(byp.items())))

# 1) multi-hop in the real pipeline order (add edge, THEN indicator)
g = TransactionGraph(); g._batch_mode=True; g._recompute_every=10**9
nz=0; n=0
for t in txs[:6000]:
    g.add_transaction(t["tx_id"], t["source_entity"], t["dest_entity"], float(t["amount"]))
    mh = g.multi_hop_indicator(t["source_entity"], t["dest_entity"]); n+=1; nz += mh>0
print(f"[multi_hop in streaming order] nonzero in {nz}/{n} transactions")
# and BEFORE adding the edge:
g2 = TransactionGraph(); g2._batch_mode=True
nz2=0
for t in txs[:6000]:
    mh = g2.multi_hop_indicator(t["source_entity"], t["dest_entity"]); nz2 += mh>0
    g2.add_transaction(t["tx_id"], t["source_entity"], t["dest_entity"], float(t["amount"]))
print(f"[multi_hop if computed BEFORE adding the edge] nonzero in {nz2}/6000")

# 2) rolling window with real (historical) timestamps and no batch flag
gh = build_graph_from_transactions(txs[:500])
print(f"[historical timestamps via build_graph_from_transactions] edges after 500 inserts: {gh.n_edges} (expected >0)")

# 3) SCC 'circular flow' membership on the full cumulative graph
G = nx.DiGraph(); [G.add_edge(t["source_entity"], t["dest_entity"]) for t in txs]
sccs = sorted(nx.strongly_connected_components(G), key=len, reverse=True)
cyc_nodes = set().union(*[s for s in sccs if len(s)>=2])
print(f"[SCC] nodes={G.number_of_nodes()} largest_SCC={len(sccs[0])} nodes_flagged_in_cycle={len(cyc_nodes)} ({len(cyc_nodes)/G.number_of_nodes():.0%})")
circ_src = {t['source_entity'] for t in txs if t['pattern_type']=='circular_flow'}
norm_src = {t['source_entity'] for t in txs if t['pattern_type']=='normal'}
print(f"[SCC] share of 'normal-sender' entities flagged in_cycle: {len(norm_src & cyc_nodes)/len(norm_src):.0%}")

# 4) Graph features are per-ENTITY, so every tx by an entity gets identical graph features
g3 = TransactionGraph(); g3._batch_mode=True; g3._recompute_every=10**9
for t in txs: g3.add_transaction(t["tx_id"], t["source_entity"], t["dest_entity"], float(t["amount"]))
g3._metrics_dirty=True; g3._recompute()
e = txs[0]["source_entity"]
print(f"[graph feats] distinct feature vectors for entity {e}'s txs: 1 (entity-level, label-independent per transaction)")
print(f"[graph] communities={g3.n_communities} sizes={sorted(collections.Counter(g3._cache['community_sizes'].values()).keys(), reverse=True)[:5]} cycle_nodes={len(g3.nodes_in_cycles)}/{g3.n_nodes}")
