"""Knowledge Graph index manager representing links between companies and properties."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.models import Company
from app.storage import JsonStorage


class GraphNode(BaseModel):
    """A node (vertex) in the knowledge graph."""

    id: str
    label: str
    attributes: Dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """A directed edge linking two nodes in the graph."""

    source: str
    target: str
    type: str


class KnowledgeGraph(BaseModel):
    """Searchable semantic network indexing companies, stacks, and locations."""

    nodes: Dict[str, GraphNode] = Field(default_factory=dict)
    edges: List[GraphEdge] = Field(default_factory=list)

    def add_node(self, node_id: str, label: str, attributes: Dict[str, Any]) -> None:
        """Add or update a node in the graph."""
        self.nodes[node_id] = GraphNode(id=node_id, label=label, attributes=attributes)

    def add_edge(self, source: str, target: str, edge_type: str) -> None:
        """Add a directed edge if it does not already exist."""
        # Avoid duplicate edges
        for edge in self.edges:
            if edge.source == source and edge.target == target and edge.type == edge_type:
                return
        self.edges.append(GraphEdge(source=source, target=target, type=edge_type))

    def rebuild_graph(self, companies: List[Company]) -> None:
        """Rebuild the entire graph index from a list of enriched companies."""
        self.nodes.clear()
        self.edges.clear()

        for co in companies:
            co_id = f"company_{co.dedupe_key()}"
            # Add Company Node
            self.add_node(
                co_id,
                "company",
                {
                    "name": co.name,
                    "domain": co.domain,
                    "industry": co.industry,
                    "ats_platform": co.ats_platform,
                },
            )

            # Skip if no intelligence profile has been generated
            if not co.intelligence:
                continue

            intel = co.intelligence

            # 1. Tech Stack Edges
            tech_fields = [
                ("languages", "uses_language"),
                ("frameworks", "uses_framework"),
                ("infrastructure", "uses_infra"),
                ("cloud", "uses_cloud"),
                ("databases", "uses_db"),
                ("ci_cd", "uses_ci_cd"),
                ("ai_stack", "uses_ai_stack"),
            ]
            for field_name, relation in tech_fields:
                tech_list = getattr(intel.engineering, field_name, [])
                for tech in tech_list:
                    tech_id = f"tech_{tech.lower().replace(' ', '_')}"
                    self.add_node(tech_id, "technology", {"name": tech})
                    self.add_edge(co_id, tech_id, relation)

            # 2. Location Edges
            for loc in intel.hiring.geographic_distribution:
                loc_id = f"loc_{loc.lower().replace(' ', '_')}"
                self.add_node(loc_id, "location", {"name": loc})
                self.add_edge(co_id, loc_id, "hires_in")

            # 3. Department Edges
            for dept in intel.hiring.departments:
                dept_id = f"dept_{dept.lower().replace('/', '_').replace(' ', '_')}"
                self.add_node(dept_id, "department", {"name": dept})
                self.add_edge(co_id, dept_id, "hires_for")

            # 4. GitHub Org Edge
            if intel.github.organization:
                github_id = f"github_org_{intel.github.organization.lower()}"
                self.add_node(github_id, "github_org", {"name": intel.github.organization})
                self.add_edge(co_id, github_id, "has_github")

    def save(self, filepath: Path, storage: Optional[JsonStorage] = None) -> None:
        """Serialize and atomically save the graph data to JSON."""
        store = storage or JsonStorage()
        data = self.model_dump(mode="json")
        store.write(filepath, data)

    def load(self, filepath: Path, storage: Optional[JsonStorage] = None) -> None:
        """Deserialize and load the graph index from disk."""
        store = storage or JsonStorage()
        if not store.exists(filepath):
            return
        try:
            data = store.read(filepath)
            if data and isinstance(data, dict):
                graph = KnowledgeGraph.model_validate(data)
                self.nodes = graph.nodes
                self.edges = graph.edges
        except Exception:
            pass
