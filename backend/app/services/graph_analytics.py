import logging
import time
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.models.graph import WorldEntity, WorldEntityVersion, WorldRelationship
from app.repositories.graph_repository import graph_repo

logger = logging.getLogger("gamemind.graph_analytics")

class GraphAnalyticsService:
    def get_topological_metrics(self, db: Session, game_project_id: str = "default_project") -> Dict[str, Any]:
        """
        Calculate graph topological metrics only from active graph state.
        Active nodes must have an active version (valid_to is null).
        Active relationships must have valid_to is null.
        """
        start_time = time.time()
        
        # 1. Fetch active entities scoped by project
        active_entities = db.query(WorldEntity).join(
            WorldEntityVersion, WorldEntity.id == WorldEntityVersion.entity_id
        ).filter(
            WorldEntityVersion.valid_to.is_(None),
            WorldEntity.game_project_id == game_project_id
        ).all()
        
        active_node_ids = {e.id for e in active_entities}
        entity_map = {e.id: e for e in active_entities}
        
        # 2. Fetch active relationships
        active_rels = db.query(WorldRelationship).filter(
            WorldRelationship.valid_to.is_(None)
        ).all()
        
        # 3. Calculate degrees (in-degree + out-degree) for active nodes
        degrees = {nid: 0 for nid in active_node_ids}
        for rel in active_rels:
            # Only count relationships where both endpoints are active nodes
            if rel.source_id in degrees and rel.target_id in degrees:
                degrees[rel.source_id] += 1
                degrees[rel.target_id] += 1
                
        # 4. Calculate metrics
        v = len(active_node_ids)
        # Filter relations that connect active nodes
        active_connected_rels = [r for r in active_rels if r.source_id in degrees and r.target_id in degrees]
        e = len(active_connected_rels)
        
        max_degree = max(degrees.values()) if degrees else 0
        avg_degree = sum(degrees.values()) / v if v > 0 else 0.0
        
        # Directed graph density: E / (V * (V - 1))
        density = float(e) / (v * (v - 1)) if v > 1 else 0.0
        
        # 5. Compile top hub nodes (sorted by degree desc, then slug asc)
        hub_list = []
        for nid, deg in degrees.items():
            ent = entity_map[nid]
            hub_list.append({
                "slug": ent.slug,
                "degree": deg
            })
            
        hub_list.sort(key=lambda x: (-x["degree"], x["slug"]))
        
        # Limit to top 5 hub nodes for representation
        top_hubs = hub_list[:5]
        
        duration = time.time() - start_time
        logger.info(f"Topological metrics calculated in {duration:.4f}s. Nodes: {v}, Edges: {e}")
        
        return {
            "active_nodes": v,
            "active_relationships": e,
            "average_degree": avg_degree,
            "max_degree": max_degree,
            "density": density,
            "hub_nodes": top_hubs
        }

graph_analytics_service = GraphAnalyticsService()
