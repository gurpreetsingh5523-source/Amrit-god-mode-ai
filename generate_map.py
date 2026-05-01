"""
generate_map.py — Amrit GodMode Codebase Brain Map Generator
=============================================================
Obsidian-style interactive force-directed graph of all Python
file dependencies. Open output brain_map.html in any browser.

Run:  python3 generate_map.py
"""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).parent

# ── Files to skip ──────────────────────────────────────────
SKIP = {
    "generate_map.py", "setup.py", "conf.py",
    "__pycache__", ".venv", "node_modules",
}

# ── Category → color mapping ───────────────────────────────
CATEGORY_COLORS = {
    "agent":    "#4fc3f7",   # blue   — agent files
    "memory":   "#81c784",   # green  — memory/store
    "llm":      "#ffb74d",   # orange — LLM/model
    "engine":   "#ce93d8",   # purple — engines/loops
    "infra":    "#f48fb1",   # pink   — infra/core
    "test":     "#fff176",   # yellow — test files
    "workspace":"#90a4ae",   # grey   — workspace files
    "other":    "#e0e0e0",   # light  — everything else
}

def categorize(name: str) -> str:
    n = name.lower()
    if n.startswith("test_") or n.endswith("_test"):
        return "test"
    if any(x in n for x in ["agent", "swarm", "queen", "worker"]):
        return "agent"
    if any(x in n for x in ["memory", "store", "episodic", "semantic", "vector", "knowledge"]):
        return "memory"
    if any(x in n for x in ["llm", "local_llm", "cloud_llm", "model", "embed", "router"]):
        return "llm"
    if any(x in n for x in ["engine", "loop", "evolution", "learning", "brain", "reasoning"]):
        return "engine"
    if any(x in n for x in ["config", "logger", "event", "state", "bus", "plugin", "policy", "permission"]):
        return "infra"
    return "other"


def extract_local_imports(filepath: Path, all_modules: set) -> list[str]:
    """Extract imports that refer to local project files only."""
    imports = []
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name.split(".")[0]
                if mod in all_modules:
                    imports.append(mod)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mod = node.module.split(".")[0]
                if mod in all_modules:
                    imports.append(mod)
    return list(set(imports))


def build_graph() -> tuple[list, list]:
    # Collect all local .py modules
    py_files = [
        f for f in ROOT.glob("*.py")  # only root-level .py files
        if f.name not in SKIP
        and not f.name.startswith(".")
        and f.stat().st_size > 0
    ]
    # Also include workspace/*.py
    for f in (ROOT / "workspace").glob("*.py"):
        if f.stat().st_size > 0:
            py_files.append(f)

    all_modules = {f.stem for f in py_files}
    nodes = []
    links = []
    node_ids = {}

    for i, f in enumerate(py_files):
        rel = str(f.relative_to(ROOT))
        stem = f.stem
        cat = categorize(stem)
        lines = len(f.read_text(encoding="utf-8", errors="ignore").splitlines())
        nodes.append({
            "id": i,
            "name": stem,
            "path": rel,
            "category": cat,
            "color": CATEGORY_COLORS[cat],
            "lines": lines,
            "size": max(6, min(24, lines // 30 + 6)),  # node radius
        })
        node_ids[stem] = i

    for f in py_files:
        stem = f.stem
        src_id = node_ids.get(stem)
        if src_id is None:
            continue
        for imp in extract_local_imports(f, all_modules):
            tgt_id = node_ids.get(imp)
            if tgt_id is not None and tgt_id != src_id:
                links.append({"source": src_id, "target": tgt_id})

    return nodes, links


def generate_html(nodes: list, links: list) -> str:
    nodes_json = json.dumps(nodes, ensure_ascii=False)
    links_json = json.dumps(links, ensure_ascii=False)
    categories = json.dumps(CATEGORY_COLORS)

    return f"""<!DOCTYPE html>
<html lang="pa">
<head>
<meta charset="UTF-8"/>
<title>ੴ Amrit GodMode — Brain Map</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:#0d1117; color:#e6edf3; font-family:'SF Mono',monospace; overflow:hidden; }}
#canvas {{ width:100vw; height:100vh; }}
#info {{
  position:fixed; top:16px; left:16px; background:rgba(22,27,34,0.95);
  border:1px solid #30363d; border-radius:12px; padding:16px 20px;
  min-width:240px; max-width:320px; z-index:10;
}}
#info h1 {{ font-size:14px; color:#58a6ff; margin-bottom:8px; letter-spacing:1px; }}
#info .stat {{ font-size:11px; color:#8b949e; margin:2px 0; }}
#info .stat b {{ color:#e6edf3; }}
#tooltip {{
  position:fixed; pointer-events:none; background:rgba(22,27,34,0.97);
  border:1px solid #58a6ff44; border-radius:8px; padding:10px 14px;
  font-size:12px; z-index:20; display:none; max-width:260px;
}}
#tooltip .t-name {{ color:#58a6ff; font-size:14px; font-weight:bold; margin-bottom:4px; }}
#tooltip .t-path {{ color:#8b949e; font-size:10px; margin-bottom:6px; }}
#tooltip .t-stat {{ color:#e6edf3; font-size:11px; }}
#legend {{
  position:fixed; bottom:16px; left:16px; background:rgba(22,27,34,0.95);
  border:1px solid #30363d; border-radius:10px; padding:12px 16px; z-index:10;
}}
#legend .l-title {{ font-size:11px; color:#8b949e; margin-bottom:8px; letter-spacing:1px; }}
#legend .l-item {{ display:flex; align-items:center; gap:8px; font-size:11px; color:#e6edf3; margin:3px 0; }}
#legend .l-dot {{ width:10px; height:10px; border-radius:50%; flex-shrink:0; }}
#search {{
  position:fixed; top:16px; right:16px; z-index:10;
}}
#search input {{
  background:rgba(22,27,34,0.95); border:1px solid #30363d;
  border-radius:8px; padding:8px 14px; color:#e6edf3;
  font-size:13px; width:200px; outline:none;
}}
#search input:focus {{ border-color:#58a6ff; }}
</style>
</head>
<body>
<div id="info">
  <h1>ੴ AMRIT BRAIN MAP</h1>
  <div class="stat">Files: <b id="s-nodes">-</b></div>
  <div class="stat">Connections: <b id="s-links">-</b></div>
  <div class="stat">Click node to highlight connections</div>
  <div class="stat">Scroll to zoom · Drag to pan</div>
</div>
<div id="legend">
  <div class="l-title">CATEGORIES</div>
  <div id="legend-items"></div>
</div>
<div id="search"><input id="search-input" placeholder="🔍 Search file..." /></div>
<div id="tooltip"></div>
<svg id="canvas"></svg>

<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
const nodes = {nodes_json};
const links = {links_json};
const CAT_COLORS = {categories};

// Stats
document.getElementById('s-nodes').textContent = nodes.length;
document.getElementById('s-links').textContent = links.length;

// Legend
const legendEl = document.getElementById('legend-items');
const catLabels = {{
  agent:'Agents', memory:'Memory', llm:'LLM/Models',
  engine:'Engines', infra:'Infrastructure', test:'Tests',
  workspace:'Workspace', other:'Other'
}};
Object.entries(CAT_COLORS).forEach(([k,c])=>{{
  legendEl.innerHTML += `<div class="l-item"><div class="l-dot" style="background:${{c}}"></div>${{catLabels[k]||k}}</div>`;
}});

const W = window.innerWidth, H = window.innerHeight;
const svg = d3.select('#canvas').attr('width',W).attr('height',H);
const g = svg.append('g');

// Zoom
svg.call(d3.zoom().scaleExtent([0.1,8]).on('zoom', e => g.attr('transform', e.transform)));

// Arrow marker
svg.append('defs').append('marker')
  .attr('id','arrow').attr('viewBox','0 -4 8 8')
  .attr('refX',18).attr('refY',0)
  .attr('markerWidth',6).attr('markerHeight',6)
  .attr('orient','auto')
  .append('path').attr('d','M0,-4L8,0L0,4').attr('fill','#30363d');

// Simulation
const sim = d3.forceSimulation(nodes)
  .force('link', d3.forceLink(links).id(d=>d.id).distance(80).strength(0.4))
  .force('charge', d3.forceManyBody().strength(-280))
  .force('center', d3.forceCenter(W/2, H/2))
  .force('collide', d3.forceCollide(d => d.size + 4));

const link = g.append('g').selectAll('line')
  .data(links).join('line')
  .attr('stroke','#30363d').attr('stroke-width',1.2)
  .attr('marker-end','url(#arrow)');

const node = g.append('g').selectAll('circle')
  .data(nodes).join('circle')
  .attr('r', d => d.size)
  .attr('fill', d => d.color)
  .attr('fill-opacity', 0.85)
  .attr('stroke', d => d.color)
  .attr('stroke-width', 1.5)
  .style('cursor','pointer')
  .call(d3.drag()
    .on('start', (e,d) => {{ if(!e.active) sim.alphaTarget(0.3).restart(); d.fx=d.x; d.fy=d.y; }})
    .on('drag',  (e,d) => {{ d.fx=e.x; d.fy=e.y; }})
    .on('end',   (e,d) => {{ if(!e.active) sim.alphaTarget(0); d.fx=null; d.fy=null; }}));

const label = g.append('g').selectAll('text')
  .data(nodes).join('text')
  .text(d => d.name)
  .attr('font-size', d => Math.max(8, d.size * 0.65))
  .attr('fill','#e6edf3').attr('text-anchor','middle')
  .attr('dy', d => d.size + 10)
  .style('pointer-events','none')
  .style('user-select','none');

// Tooltip
const tip = document.getElementById('tooltip');
node.on('mousemove', (e,d) => {{
  const ins = links.filter(l => l.source.id===d.id || l.target.id===d.id).length;
  tip.style.display='block';
  tip.style.left = (e.clientX+16)+'px';
  tip.style.top  = (e.clientY-10)+'px';
  tip.innerHTML = `
    <div class="t-name">${{d.name}}</div>
    <div class="t-path">${{d.path}}</div>
    <div class="t-stat">📄 ${{d.lines}} lines &nbsp;|&nbsp; 🔗 ${{ins}} connections</div>
    <div class="t-stat">🏷 ${{d.category}}</div>`;
}}).on('mouseleave', () => tip.style.display='none');

// Click to highlight
let selected = null;
node.on('click', (e,d) => {{
  e.stopPropagation();
  if(selected === d.id) {{
    selected = null;
    node.attr('fill-opacity',0.85).attr('stroke-width',1.5);
    link.attr('stroke','#30363d').attr('stroke-opacity',1).attr('stroke-width',1.2);
  }} else {{
    selected = d.id;
    const connected = new Set();
    connected.add(d.id);
    links.forEach(l => {{
      if(l.source.id===d.id) connected.add(l.target.id);
      if(l.target.id===d.id) connected.add(l.source.id);
    }});
    node.attr('fill-opacity', n => connected.has(n.id)?1:0.15)
        .attr('stroke-width',  n => n.id===d.id?3:1.5);
    link.attr('stroke', l => (l.source.id===d.id||l.target.id===d.id)?l.source.color||'#58a6ff':'#30363d')
        .attr('stroke-opacity', l => (l.source.id===d.id||l.target.id===d.id)?1:0.1)
        .attr('stroke-width',   l => (l.source.id===d.id||l.target.id===d.id)?2:1.2);
  }}
}});
svg.on('click', () => {{
  selected=null;
  node.attr('fill-opacity',0.85).attr('stroke-width',1.5);
  link.attr('stroke','#30363d').attr('stroke-opacity',1).attr('stroke-width',1.2);
}});

// Search
document.getElementById('search-input').addEventListener('input', function() {{
  const q = this.value.toLowerCase().trim();
  if(!q) {{
    node.attr('fill-opacity',0.85);
    label.attr('fill','#e6edf3');
    return;
  }}
  node.attr('fill-opacity', d => d.name.toLowerCase().includes(q)?1:0.1);
  label.attr('fill', d => d.name.toLowerCase().includes(q)?'#58a6ff':'#30363d');
}});

sim.on('tick', () => {{
  link.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y)
      .attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
  node.attr('cx',d=>d.x).attr('cy',d=>d.y);
  label.attr('x',d=>d.x).attr('y',d=>d.y);
}});
</script>
</body>
</html>"""


if __name__ == "__main__":
    print("🧠 Amrit Brain Map — ਬਣ ਰਿਹਾ ਹੈ...")
    nodes, links = build_graph()
    html = generate_html(nodes, links)
    out = ROOT / "brain_map.html"
    out.write_text(html, encoding="utf-8")
    print(f"✅ {len(nodes)} files | {len(links)} connections")
    print(f"📄 Saved: {out}")
    print("🌐 ਖੋਲ੍ਹੋ: open brain_map.html")
