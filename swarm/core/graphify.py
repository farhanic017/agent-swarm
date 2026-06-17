from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from swarm.core.file_access import assert_allowed_path


@dataclass(frozen=True)
class GraphifyNode:
    id: str
    label: str
    kind: str = "concept"

    def to_dict(self) -> dict:
        return {"id": self.id, "label": self.label, "kind": self.kind}


@dataclass(frozen=True)
class GraphifyEdge:
    source: str
    target: str
    relation: str = "related_to"

    def to_dict(self) -> dict:
        return {"source": self.source, "target": self.target, "relation": self.relation}


def build_graphify_payload(title: str, nodes: list[dict] | None = None, edges: list[dict] | None = None) -> dict:
    clean_nodes = [_normalize_node(node, idx) for idx, node in enumerate(nodes or [])]
    if not clean_nodes:
        clean_nodes = [
            GraphifyNode("project", title, "project").to_dict(),
            GraphifyNode("agents", "Agent Swarm", "system").to_dict(),
            GraphifyNode("security", "Scoped File Access", "safety").to_dict(),
        ]
    node_ids = {node["id"] for node in clean_nodes}
    clean_edges = []
    for edge in edges or []:
        source = str(edge.get("source") or "").strip()
        target = str(edge.get("target") or "").strip()
        if source in node_ids and target in node_ids:
            clean_edges.append(GraphifyEdge(source, target, str(edge.get("relation") or edge.get("type") or "related_to")).to_dict())
    if not clean_edges and len(clean_nodes) > 1:
        root = clean_nodes[0]["id"]
        clean_edges = [GraphifyEdge(root, node["id"], "contains").to_dict() for node in clean_nodes[1:]]
    return {
        "format": "graphify",
        "version": 1,
        "title": title,
        "nodes": clean_nodes,
        "edges": clean_edges,
        "views": {
            "default": "force",
            "group_by": "kind",
            "show_labels": True,
        },
    }


def build_graphify_project_map(project_name: str, agents: list[str] | None = None, artifacts: list[str] | None = None) -> dict:
    nodes = [{"id": "project", "label": project_name, "kind": "project"}]
    edges = []
    for agent in agents or []:
        node_id = f"agent:{_slug(agent)}"
        nodes.append({"id": node_id, "label": agent, "kind": "agent"})
        edges.append({"source": "project", "target": node_id, "relation": "uses_agent"})
    for artifact in artifacts or []:
        node_id = f"artifact:{_slug(artifact)}"
        nodes.append({"id": node_id, "label": artifact, "kind": "artifact"})
        edges.append({"source": "project", "target": node_id, "relation": "produces"})
    return build_graphify_payload(project_name, nodes, edges)


def export_graphify_payload(payload: dict, path: str) -> str:
    target = assert_allowed_path(path, "write")
    if not target.parent.exists():
        raise FileNotFoundError(str(target.parent))
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(target)


def _normalize_node(node: dict, idx: int) -> dict:
    label = str(node.get("label") or node.get("name") or f"Node {idx + 1}").strip()
    node_id = str(node.get("id") or _slug(label) or f"node-{idx + 1}").strip()
    kind = str(node.get("kind") or node.get("type") or "concept").strip()
    return GraphifyNode(node_id, label, kind).to_dict()


def _slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "item"
