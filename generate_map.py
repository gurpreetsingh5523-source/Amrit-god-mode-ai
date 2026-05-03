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



CATEGORY_COLORS = {
    'agent': '#539bf5', 'memory': '#f97306', 'llm': '#d29034',
    'engine': '#b16cbe', 'infra': '#8cb44e', 'test': '#e03f3f',
    'workspace': '#5eb95e', 'other': '#a77afe'
}

def generate_html(nodes: list, links: list) -> str:
    nodes_json = json.dumps(nodes, ensure_ascii=False)
    links_json = json.dumps(links, ensure_ascii=False)
    categories = json.dumps(CATEGORY_COLORS)

    return f"""<!DOCTYPE html>
<html lang="pa">
<head>
<meta charset="UTF-8"/>
<title>ੴ Amrit GodMode — Brain Map</title>
<style>{CSS_STYLE}</style>
</head>
<body>
{HTML_BODY}
<script src="https://d3js.org/d3.v7.min.js"></script>
<script>{JS_SCRIPT.format(nodes_json=nodes_json, links_json=links_json, categories=categories)}</script>
</body>
</html>"""

CSS_STYLE = """
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
"""

HTML_BODY = """
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
"""

JS_SCRIPT = """
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
  .attr('refY',0)
  .attr('markerWidth', 10).attr('markerHeight', 10).attr('orient', 'auto');

// Draw arrowhead
svg.append('line')
  .attr('id', 'arrow-head')
  .attr('x1', 18).attr('y1', 0)
  .attr('x2', 28).attr('y2', -5)
  .attr('stroke', '#000').attr('marker-end', 'url(#arrow)');

// Arrow marker end
svg.append('defs').append('marker')
  .attr('id', 'arrow')
  .attr('viewBox', '0 0 10 10').attr('refX', 8).attr('markerWidth', 4).attr('markerHeight', 4);

// Draw arrow path
svg.append('path')
  .attr('id', 'arrow-path')
  .attr('d', 'M0,5H10M7,2L10,5L7,8')
  .attr('stroke', '#000').attr('fill', 'none');

// Arrow marker end
svg.append('use')
  .attr('xlink:href', '#arrow-head')
  .attr('x', 28).attr('y', -5);

// Arrow marker start
svg.append('use')
  .attr('xlink:href', '#arrow-path')
  .attr('x', 0).attr('y', 5);

// Node elements
const node = g.selectAll('.node').data(nodes).enter().append('circle')
  .attr('class', 'node')
  .attr('r', d => Math.max(8, d.size * 0.65))
  .attr('cx', d => d.x).attr('cy', d => d.y)
  .style('fill', d => d.category ? CATEGORY_COLORS[d.category] : 'grey');

const label = g.selectAll('.label').data(nodes).enter().append('text')
  .text(d => d.name)
  .attr('class', 'label')
  .attr('font-size', d => Math.max(8, d.size * 0.65))
  .attr('fill', '#e6edf3').attr('text-anchor', 'middle')
  .attr('x', d => d.x).attr('y', d => d.y + (d.size * 2));

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
  `;
}}).on('mouseout', (e) => {{
  tip.style.display='none';
}});
"""


if __name__ == "__main__":
    print("🧠 Amrit Brain Map — ਬਣ ਰਿਹਾ ਹੈ...")
    nodes, links = build_graph()
    html = generate_html(nodes, links)
    out = ROOT / "brain_map.html"
    out.write_text(html, encoding="utf-8")
    print(f"✅ {len(nodes)} files | {len(links)} connections")
    print(f"📄 Saved: {out}")
    print("🌐 ਖੋਲ੍ਹੋ: open brain_map.html")