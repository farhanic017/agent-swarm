"""Knowledge Graph tools — let agents navigate the project knowledge graph.

Reads `.understand-anything/knowledge-graph.json` (the graph built by
/understand) and provides query, navigation, and exploration tools.

Tools:
  - graph_search(query)     — find nodes by keyword
  - graph_neighbors(node_id) — get neighbors of a node with edge types
  - graph_path(source, target) — find shortest path between two concepts
  - graph_explain(node_id)  — explain a specific node with all connections
  - graph_stats()           — get graph overview statistics
"""

from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Optional


def _find_graph(project_root: str = "") -> Optional[Path]:
    """Find the knowledge graph JSON in the project directory."""
    candidates = [
        Path(project_root) / ".understand-anything" / "knowledge-graph.json",
        Path(project_root) / "graphify-out" / "graph.json",
        Path.cwd() / ".understand-anything" / "knowledge-graph.json",
        Path.cwd() / "graphify-out" / "graph.json",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _load_graph(path: Optional[Path] = None) -> dict:
    """Load the knowledge graph from disk."""
    graph_path = path or _find_graph()
    if not graph_path or not graph_path.exists():
        return {"nodes": [], "edges": [], "project": {}, "layers": [], "tour": []}
    try:
        data = json.loads(graph_path.read_text(encoding="utf-8"))
        return data
    except (json.JSONDecodeError, Exception):
        return {"nodes": [], "edges": [], "project": {}, "layers": [], "tour": []}


def _find_nodes(graph: dict, query: str, limit: int = 20) -> list[dict]:
    """Find nodes matching a keyword query (fuzzy match on name, summary, tags)."""
    query_lower = query.lower()
    scored = []
    for node in graph.get("nodes", []):
        score = 0
        name = (node.get("name") or "").lower()
        summary = (node.get("summary") or "").lower()
        tags = " ".join(node.get("tags") or []).lower()

        if query_lower in name:
            score += 10
        if query_lower in tags:
            score += 5
        if query_lower in summary:
            score += 2

        if score > 0:
            scored.append((score, node))

    scored.sort(key=lambda x: -x[0])
    return [n for _, n in scored[:limit]]


def _build_node_label(graph: dict, node_id: str) -> str:
    """Build a human-readable label for a node ID."""
    for node in graph.get("nodes", []):
        if node.get("id") == node_id:
            return f"{node.get('name', node_id)} ({node.get('type', 'unknown')})"
    return node_id


# ── Public tool functions (called via ToolRegistry) ───────────────────


def graph_search(query: str, limit: int = 20) -> str:
    """Search the project knowledge graph for nodes matching a query.

    Args:
        query: Search term to find matching code concepts, files, and modules.
        limit: Maximum results to return (default 20).

    Returns:
        Formatted list of matching nodes with their descriptions.
    """
    graph = _load_graph()
    if not graph.get("nodes"):
        return "No knowledge graph found. Run `/understand` first to analyze the project."

    matches = _find_nodes(graph, query, limit)
    if not matches:
        return f"No nodes matching '{query}' in the knowledge graph."

    lines = [f"Found {len(matches)} node(s) matching '{query}':"]
    for node in matches:
        tags = ", ".join(node.get("tags", [])[:5])
        lines.append(f"\n  [{node.get('type', '?')}] {node.get('name', '?')}")
        lines.append(f"    ID: {node.get('id', '?')}")
        lines.append(f"    File: {node.get('filePath', 'N/A')}")
        lines.append(f"    Summary: {node.get('summary', 'N/A')[:200]}")
        if tags:
            lines.append(f"    Tags: {tags}")
    return "\n".join(lines)


def graph_neighbors(node_id: str, max_neighbors: int = 30) -> str:
    """Get all neighbors of a node in the knowledge graph.

    Shows what a node connects to, with edge types and directions.

    Args:
        node_id: The node ID to explore (e.g., 'file:src/main.ts').
        max_neighbors: Maximum neighbors to return (default 30).

    Returns:
        Formatted list of connected nodes with edge relationships.
    """
    graph = _load_graph()
    if not graph.get("nodes"):
        return "No knowledge graph found."

    node_exists = any(n.get("id") == node_id for n in graph["nodes"])
    if not node_exists:
        return f"Node '{node_id}' not found in the knowledge graph."

    label = _build_node_label(graph, node_id)
    lines = [f"Connections for {label}:"]

    outgoing = []
    incoming = []
    for edge in graph.get("edges", []):
        if edge.get("source") == node_id:
            outgoing.append(edge)
        if edge.get("target") == node_id:
            incoming.append(edge)

    if outgoing:
        lines.append(f"\n  Outgoing ({len(outgoing)}):")
        for edge in outgoing[:max_neighbors]:
            target = _build_node_label(graph, edge.get("target", "?"))
            rel = edge.get("type", "connected_to")
            conf = edge.get("weight", "")
            conf_str = f" [{conf}]" if conf else ""
            lines.append(f"    --{rel}{conf_str}--> {target}")

    if incoming:
        lines.append(f"\n  Incoming ({len(incoming)}):")
        for edge in incoming[:max_neighbors]:
            source = _build_node_label(graph, edge.get("source", "?"))
            rel = edge.get("type", "connected_to")
            conf = edge.get("weight", "")
            conf_str = f" [{conf}]" if conf else ""
            lines.append(f"    {source} --{rel}{conf_str}-->")

    total = len(outgoing) + len(incoming)
    if total == 0:
        lines.append("  (no connections)")

    return "\n".join(lines)


def graph_path(source_query: str, target_query: str) -> str:
    """Find the shortest path between two concepts in the knowledge graph.

    Uses BFS to trace the connection chain between two nodes.

    Args:
        source_query: Keyword to find the starting concept.
        target_query: Keyword to find the ending concept.

    Returns:
        The path with each hop explained, or an error message.
    """
    graph = _load_graph()
    if not graph.get("nodes"):
        return "No knowledge graph found."

    sources = _find_nodes(graph, source_query, 5)
    targets = _find_nodes(graph, target_query, 5)
    if not sources:
        return f"No nodes matching '{source_query}'."
    if not targets:
        return f"No nodes matching '{target_query}'."

    # Build adjacency map
    adj: dict[str, list[tuple[str, str]]] = {}
    for edge in graph.get("edges", []):
        src = edge.get("source", "")
        tgt = edge.get("target", "")
        rel = edge.get("type", "connected_to")
        adj.setdefault(src, []).append((tgt, rel))
        adj.setdefault(tgt, []).append((src, rel))

    # BFS from each source to each target
    import collections
    best_path = None
    for s_node in sources:
        sid = s_node.get("id", "")
        for t_node in targets:
            tid = t_node.get("id", "")
            if sid == tid:
                best_path = [sid]
                break

            visited = {sid}
            queue = collections.deque([(sid, [sid])])
            while queue:
                current, path = queue.popleft()
                if current == tid:
                    if best_path is None or len(path) < len(best_path):
                        best_path = path
                    break
                for neighbor, _ in adj.get(current, []):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, path + [neighbor]))

    if not best_path:
        return f"No path found between '{source_query}' and '{target_query}'."

    lines = [f"Path ({len(best_path) - 1} hops):"]
    for i, nid in enumerate(best_path):
        label = _build_node_label(graph, nid)
        lines.append(f"  {i + 1}. {label}")
        if i < len(best_path) - 1:
            for edge in graph.get("edges", []):
                if edge.get("source") == nid and edge.get("target") == best_path[i + 1]:
                    lines[-1] += f"\n     --{edge.get('type', 'connected_to')}-->"
                    break
                if edge.get("source") == best_path[i + 1] and edge.get("target") == nid:
                    lines[-1] += f"\n     <--{edge.get('type', 'connected_to')}--"
                    break

    return "\n".join(lines)


def graph_explain(node_id: str) -> str:
    """Get a detailed explanation of a specific node in the knowledge graph.

    Shows the node's full metadata, its connections, and which tour steps
    and layers reference it.

    Args:
        node_id: The node ID to explain.

    Returns:
        Detailed explanation with all metadata and connections.
    """
    graph = _load_graph()
    if not graph.get("nodes"):
        return "No knowledge graph found."

    node = None
    for n in graph["nodes"]:
        if n.get("id") == node_id:
            node = n
            break

    if not node:
        return f"Node '{node_id}' not found."

    lines = [f"=== {node.get('name', node_id)} ==="]
    lines.append(f"  Type: {node.get('type', 'N/A')}")
    lines.append(f"  File: {node.get('filePath', 'N/A')}")
    lines.append(f"  Summary: {node.get('summary', 'N/A')}")
    if node.get("tags"):
        lines.append(f"  Tags: {', '.join(node['tags'])}")
    if node.get("complexity"):
        lines.append(f"  Complexity: {node.get('complexity')}")
    if node.get("languageNotes"):
        lines.append(f"  Notes: {node.get('languageNotes')}")
    if node.get("source_location"):
        lines.append(f"  Location: {node.get('source_location')}")

    # Edge summary
    outgoing = []
    incoming = []
    for edge in graph.get("edges", []):
        if edge.get("source") == node_id:
            outgoing.append(edge)
        if edge.get("target") == node_id:
            incoming.append(edge)

    if outgoing:
        lines.append(f"\n  Depends on / connects to ({len(outgoing)}):")
        for e in outgoing[:10]:
            tgt = _build_node_label(graph, e.get("target", "?"))
            lines.append(f"    -> {tgt} [{e.get('type', 'connected_to')}]")
    if incoming:
        lines.append(f"\n  Used by / referenced from ({len(incoming)}):")
        for e in incoming[:10]:
            src = _build_node_label(graph, e.get("source", "?"))
            lines.append(f"    <- {src} [{e.get('type', 'connected_to')}]")

    # Layer membership
    for layer in graph.get("layers", []):
        if node_id in layer.get("nodeIds", []):
            lines.append(f"\n  Layer: {layer.get('name', '?')} — {layer.get('description', '')[:100]}")

    # Tour step membership
    for step in graph.get("tour", []):
        if node_id in step.get("nodeIds", []):
            lines.append(f"\n  Tour Step {step.get('order', '?')}: {step.get('title', '?')}")

    return "\n".join(lines)


def graph_stats() -> str:
    """Get statistics and overview of the project knowledge graph.

    Returns node counts by type, edge counts by type, layer list, and
    community data if available.

    Returns:
        Formatted statistics about the knowledge graph.
    """
    graph = _load_graph()
    if not graph.get("nodes"):
        return "No knowledge graph found. Run `/understand` first."

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    layers = graph.get("layers", [])
    tour = graph.get("tour", [])
    project = graph.get("project", {})

    lines = []

    if project:
        lines.append(f"Project: {project.get('name', 'Unnamed')}")
        lines.append(f"  Description: {project.get('description', '')[:150]}")
        lines.append(f"  Languages: {', '.join(project.get('languages', []))}")
        lines.append(f"  Frameworks: {', '.join(project.get('frameworks', []))}")
        if project.get("analyzedAt"):
            lines.append(f"  Analyzed: {project['analyzedAt']}")
        lines.append("")

    lines.append(f"Total Nodes: {len(nodes)}")
    by_type: dict[str, int] = {}
    for n in nodes:
        t = n.get("type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1
    for t, c in sorted(by_type.items(), key=lambda x: -x[1]):
        lines.append(f"  {t}: {c}")

    lines.append(f"\nTotal Edges: {len(edges)}")
    by_etype: dict[str, int] = {}
    for e in edges:
        t = e.get("type", "unknown")
        by_etype[t] = by_etype.get(t, 0) + 1
    for t, c in sorted(by_etype.items(), key=lambda x: -x[1])[:15]:
        lines.append(f"  {t}: {c}")

    if layers:
        lines.append(f"\nLayers ({len(layers)}):")
        for layer in layers:
            count = len(layer.get("nodeIds", []))
            lines.append(f"  {layer.get('name', '?')} ({count} nodes) — {layer.get('description', '')[:100]}")

    if tour:
        lines.append(f"\nTour Steps: {len(tour)}")

    # God nodes (most connected)
    degree: dict[str, int] = {}
    for e in edges:
        degree[e.get("source", "")] = degree.get(e.get("source", ""), 0) + 1
        degree[e.get("target", "")] = degree.get(e.get("target", ""), 0) + 1
    if degree:
        top = sorted(degree.items(), key=lambda x: -x[1])[:5]
        lines.append("\nMost Connected Nodes:")
        for nid, d in top:
            label = _build_node_label(graph, nid)
            lines.append(f"  {label} ({d} connections)")

    return "\n".join(lines)
