import hashlib
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session
from app.models.graph import WorldEntity, WorldEntityVersion, WorldRelationship
from app.repositories.graph_repository import graph_repo
from app.services.graph_cache import graph_cache
from app.services.telemetry import telemetry_service

class GraphTraversalService:
    # Frozen Safety Limits
    MAX_DEPTH = 4
    MAX_SUBGRAPH_NODES = 100
    MAX_SUBGRAPH_EDGES = 500
    MAX_PATH_RESULTS = 25

    def _get_subgraph_hash(self, seeds: List[str]) -> str:
        """Generate a stable MD5 hash for a list of seed slugs."""
        sorted_seeds = sorted(list(set(seeds)))
        seed_str = ",".join(sorted_seeds)
        return hashlib.md5(seed_str.encode("utf-8")).hexdigest()

    def get_subgraph(
        self,
        db: Session,
        seeds: List[str],
        depth: int = 2,
        max_nodes: int = 100,
        max_edges: int = 500,
        direction: str = "both",
        as_of: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Extract the subgraph neighborhood around a set of seed slugs up to depth hops.
        Enforces safety limits and utilizes version-stamp invalidation caching.
        """
        # Validate safety limits
        if depth > self.MAX_DEPTH:
            raise ValueError(f"Requested traversal depth exceeds maximum allowed depth of {self.MAX_DEPTH}")
        if max_nodes > self.MAX_SUBGRAPH_NODES:
            raise ValueError(f"Requested node limit exceeds maximum allowed of {self.MAX_SUBGRAPH_NODES}")
        if max_edges > self.MAX_SUBGRAPH_EDGES:
            raise ValueError(f"Requested edge limit exceeds maximum allowed of {self.MAX_SUBGRAPH_EDGES}")

        # Construct cache query prefix
        subgraph_hash = self._get_subgraph_hash(seeds)
        # Include as_of in query prefix if it exists to keep different temporal queries separate
        as_of_str = as_of.isoformat() if as_of else "current"
        query_prefix = f"graph:subgraph:{subgraph_hash}:{depth}:{max_nodes}:{max_edges}:{direction}:{as_of_str}"

        # 1. Check Cache
        cached_data, is_hit = graph_cache.get_cached_traversal(query_prefix)
        if is_hit:
            # Record hit telemetry
            telemetry_service.record_metric("graph_subgraph_retrievals_total", 1, {"cache": "hit"})
            return cached_data

        # 2. Cache Miss: Run DB Traversal
        start_time = time.time()

        # Find seed entities
        seed_entities = []
        for slug in seeds:
            ent = graph_repo.get_entity_by_slug(db, slug)
            if ent:
                seed_entities.append(ent)

        if not seed_entities:
            # Empty subgraph
            result = {"nodes": [], "edges": []}
            graph_cache.set_cached_traversal(query_prefix, result, [], [])
            telemetry_service.record_metric("graph_subgraph_retrievals_total", 1, {"cache": "miss"})
            return result

        # Initialize collections
        # map entity_id -> WorldEntity
        nodes_map: Dict[str, WorldEntity] = {}
        # map relationship key (source_id, target_id, rel_type) -> WorldRelationship
        edges_map: Dict[Tuple[str, str, str], WorldRelationship] = {}

        # Set of node IDs to expand at the current level
        current_level_nodes = set()
        for ent in seed_entities:
            nodes_map[str(ent.id)] = ent
            current_level_nodes.add(ent.id)

        # Truncate nodes if seeds exceed max_nodes
        if len(nodes_map) > max_nodes:
            # Slice nodes map to fit max_nodes
            truncated_ids = list(nodes_map.keys())[:max_nodes]
            nodes_map = {nid: nodes_map[nid] for nid in truncated_ids}
            current_level_nodes = set(uuid.UUID(nid) for nid in truncated_ids)

        # Traverse level-by-level
        for level in range(1, depth + 1):
            if not current_level_nodes or len(nodes_map) >= max_nodes or len(edges_map) >= max_edges:
                break

            next_level_nodes = set()
            for node_id in current_level_nodes:
                if len(nodes_map) >= max_nodes and node_id not in [uuid.UUID(nid) for nid in nodes_map]:
                    continue

                # Query adjacent edges
                rels = graph_repo.get_adjacent_relationships(db, node_id, direction=direction, as_of=as_of)
                
                for rel in rels:
                    # Enforce max edges limit
                    if len(edges_map) >= max_edges:
                        break

                    # Identify the neighbor entity ID
                    neighbor_id = rel.target_id if rel.source_id == node_id else rel.source_id

                    # Check if neighbor is already collected or if we can collect it
                    neighbor_collected = str(neighbor_id) in nodes_map
                    if not neighbor_collected:
                        # Enforce max nodes limit
                        if len(nodes_map) >= max_nodes:
                            continue
                        
                        # Load neighbor entity
                        neighbor_ent = db.query(WorldEntity).filter(WorldEntity.id == neighbor_id).first()
                        if neighbor_ent:
                            nodes_map[str(neighbor_ent.id)] = neighbor_ent
                            next_level_nodes.add(neighbor_id)
                    else:
                        if neighbor_id not in current_level_nodes: # Avoid re-expanding visited nodes at previous levels
                            next_level_nodes.add(neighbor_id)

                    # Add edge
                    edge_key = (str(rel.source_id), str(rel.target_id), rel.rel_type)
                    edges_map[edge_key] = rel

            current_level_nodes = next_level_nodes

        # Format nodes and edges for output
        nodes_out = []
        involved_entities = []
        for ent_id_str, ent in nodes_map.items():
            version_info = graph_repo.get_active_entity_version(db, ent.id, as_of=as_of)
            nodes_out.append({
                "slug": ent.slug,
                "entity_type": ent.entity_type,
                "name": version_info.name if version_info else ent.slug,
                "description": version_info.description if version_info else "",
                "importance_score": version_info.importance_score if version_info else 0,
                "properties": version_info.properties if version_info else {},
                "valid_from": version_info.valid_from.isoformat() if version_info else ent.created_at.isoformat(),
                "valid_to": version_info.valid_to.isoformat() if version_info and version_info.valid_to else None
            })
            involved_entities.append(ent.slug)

        # Get entity ID to slug mapping to resolve source/target slugs
        id_to_slug = {str(ent.id): ent.slug for ent in nodes_map.values()}
        
        edges_out = []
        involved_relationships = []
        for rel in edges_map.values():
            src_slug = id_to_slug.get(str(rel.source_id))
            tgt_slug = id_to_slug.get(str(rel.target_id))
            
            # If the neighbor node was excluded due to node limit, the slug might be missing in id_to_slug.
            # In that case, look it up in DB to be safe
            if not src_slug:
                src_ent = db.query(WorldEntity).filter(WorldEntity.id == rel.source_id).first()
                src_slug = src_ent.slug if src_ent else str(rel.source_id)
            if not tgt_slug:
                tgt_ent = db.query(WorldEntity).filter(WorldEntity.id == rel.target_id).first()
                tgt_slug = tgt_ent.slug if tgt_ent else str(rel.target_id)

            edges_out.append({
                "source": src_slug,
                "target": tgt_slug,
                "rel_type": rel.rel_type,
                "weight": rel.weight,
                "valid_from": rel.valid_from.isoformat(),
                "valid_to": rel.valid_to.isoformat() if rel.valid_to else None,
                "properties": rel.properties
            })
            involved_relationships.append((src_slug, tgt_slug, rel.rel_type))

        result = {
            "nodes": nodes_out,
            "edges": edges_out
        }

        # 3. Cache the traversal result
        graph_cache.set_cached_traversal(
            query_prefix=query_prefix,
            result_data=result,
            involved_entities=involved_entities,
            involved_relationships=involved_relationships
        )

        # Record telemetry metrics
        duration = time.time() - start_time
        telemetry_service.record_metric("graph_subgraph_retrievals_total", 1, {"cache": "miss"})
        telemetry_service.record_metric("graph_traversal_duration_seconds", duration, {"algorithm": "subgraph"})

        return result

    def traverse(
        self,
        db: Session,
        source: str,
        target: str,
        depth: int = 4,
        max_paths: int = 25,
        algorithm: str = "bfs",
        as_of: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Find path options between source and target slugs.
        Enforces safety limits, records depth/path limit telemetry, and uses version stamp caching.
        """
        # Validate safety limits
        if depth > self.MAX_DEPTH:
            raise ValueError(f"Requested traversal depth exceeds maximum allowed depth of {self.MAX_DEPTH}")
        if max_paths > self.MAX_PATH_RESULTS:
            raise ValueError(f"Requested path limit exceeds maximum allowed of {self.MAX_PATH_RESULTS}")

        as_of_str = as_of.isoformat() if as_of else "current"
        query_prefix = f"graph:path:{source}:{target}:{depth}:{max_paths}:{algorithm}:{as_of_str}"

        # 1. Check Cache
        cached_data, is_hit = graph_cache.get_cached_traversal(query_prefix)
        if is_hit:
            return cached_data

        # 2. Cache Miss: Run Traversal
        start_time = time.time()

        source_ent = graph_repo.get_entity_by_slug(db, source)
        target_ent = graph_repo.get_entity_by_slug(db, target)

        if not source_ent or not target_ent:
            # If either node doesn't exist, no paths can be found
            result = {"paths": []}
            # Cache the empty result involving the present node slug
            involved_ents = [s for s in [source, target] if s]
            graph_cache.set_cached_traversal(query_prefix, result, involved_ents, [])
            return result

        paths = []
        involved_entities = set()
        involved_relationships = set()

        if algorithm.lower() == "bfs":
            # Queue-based BFS for unweighted shortest path
            # Each entry in queue: (current_node_id, current_slug, path_nodes_slugs, path_edges_list)
            from collections import deque
            queue = deque([(source_ent.id, source_ent.slug, [source_ent.slug], [])])
            visited = {source_ent.id}

            while queue:
                curr_id, curr_slug, path_nodes, path_edges = queue.popleft()

                if curr_id == target_ent.id:
                    # Found shortest path!
                    paths.append({
                        "nodes": path_nodes,
                        "edges": [
                            {
                                "source": id_to_slug.get(str(rel.source_id), str(rel.source_id)),
                                "target": id_to_slug.get(str(rel.target_id), str(rel.target_id)),
                                "rel_type": rel.rel_type,
                                "weight": rel.weight,
                                "properties": rel.properties
                            } for rel in path_edges
                        ]
                    })
                    
                    # Track involved entities and relationships
                    for node in path_nodes:
                        involved_entities.add(node)
                    for rel in path_edges:
                        # Resolve slugs
                        src_slug = source if rel.source_id == source_ent.id else (target if rel.source_id == target_ent.id else "")
                        tgt_slug = source if rel.target_id == source_ent.id else (target if rel.target_id == target_ent.id else "")
                        # Fallback to DB query if needed to resolve slugs
                        if not src_slug:
                            se = db.query(WorldEntity).filter(WorldEntity.id == rel.source_id).first()
                            src_slug = se.slug if se else str(rel.source_id)
                        if not tgt_slug:
                            te = db.query(WorldEntity).filter(WorldEntity.id == rel.target_id).first()
                            tgt_slug = te.slug if te else str(rel.target_id)
                        
                        involved_relationships.add((src_slug, tgt_slug, rel.rel_type))
                        involved_entities.add(src_slug)
                        involved_entities.add(tgt_slug)
                    
                    break # Only shortest path is needed for BFS

                if len(path_edges) >= depth:
                    continue

                # Query active outgoing relationships
                rels = graph_repo.get_adjacent_relationships(db, curr_id, direction="out", as_of=as_of)
                
                # Pre-fetch neighbor entity details to build slug map
                neighbor_ids = [rel.target_id for rel in rels if rel.target_id not in visited]
                if neighbor_ids:
                    neighbors = db.query(WorldEntity).filter(WorldEntity.id.in_(neighbor_ids)).all()
                    id_to_slug = {str(n.id): n.slug for n in neighbors}
                    id_to_ent = {n.id: n for n in neighbors}
                else:
                    id_to_slug = {}
                    id_to_ent = {}

                # Include source/target in slug map
                id_to_slug[str(source_ent.id)] = source_ent.slug
                id_to_slug[str(target_ent.id)] = target_ent.slug

                for rel in rels:
                    neighbor_id = rel.target_id
                    if neighbor_id not in visited:
                        neighbor_ent = id_to_ent.get(neighbor_id)
                        if not neighbor_ent:
                            continue
                        
                        visited.add(neighbor_id)
                        queue.append((
                            neighbor_id,
                            neighbor_ent.slug,
                            path_nodes + [neighbor_ent.slug],
                            path_edges + [rel]
                        ))

        elif algorithm.lower() == "dfs":
            # DFS exploration with limits
            path_limit_hit = [False]
            depth_reached = [0]

            def dfs_recurse(
                curr_id: uuid.UUID,
                curr_slug: str,
                path_nodes: List[str],
                path_edges: List[WorldRelationship],
                visited: Set[uuid.UUID],
                curr_depth: int
            ):
                if len(paths) >= max_paths:
                    path_limit_hit[0] = True
                    return
                if curr_depth > depth:
                    depth_reached[0] = max(depth_reached[0], curr_depth - 1)
                    return

                depth_reached[0] = max(depth_reached[0], curr_depth)

                if curr_id == target_ent.id:
                    # Resolve relationships to dicts
                    edges_out = []
                    for rel in path_edges:
                        # Resolve slugs
                        src_slug = path_nodes[path_nodes.index(curr_slug) - 1] # rough approximation or lookup
                        # Fetch correct slugs from DB to prevent any ordering mismatch
                        src_ent = db.query(WorldEntity).filter(WorldEntity.id == rel.source_id).first()
                        tgt_ent = db.query(WorldEntity).filter(WorldEntity.id == rel.target_id).first()
                        s_slug = src_ent.slug if src_ent else str(rel.source_id)
                        t_slug = tgt_ent.slug if tgt_ent else str(rel.target_id)
                        
                        edges_out.append({
                            "source": s_slug,
                            "target": t_slug,
                            "rel_type": rel.rel_type,
                            "weight": rel.weight,
                            "properties": rel.properties
                        })
                        involved_relationships.add((s_slug, t_slug, rel.rel_type))
                        involved_entities.add(s_slug)
                        involved_entities.add(t_slug)

                    paths.append({
                        "nodes": list(path_nodes),
                        "edges": edges_out
                    })
                    
                    for node in path_nodes:
                        involved_entities.add(node)
                    
                    if len(paths) >= max_paths:
                        path_limit_hit[0] = True
                    return

                # Fetch adjacent outgoing relationships
                rels = graph_repo.get_adjacent_relationships(db, curr_id, direction="out", as_of=as_of)
                for rel in rels:
                    if len(paths) >= max_paths:
                        break
                    
                    neighbor_id = rel.target_id
                    if neighbor_id not in visited:
                        neighbor_ent = db.query(WorldEntity).filter(WorldEntity.id == neighbor_id).first()
                        if not neighbor_ent:
                            continue
                        
                        visited.add(neighbor_id)
                        dfs_recurse(
                            curr_id=neighbor_id,
                            curr_slug=neighbor_ent.slug,
                            path_nodes=path_nodes + [neighbor_ent.slug],
                            path_edges=path_edges + [rel],
                            visited=visited,
                            curr_depth=curr_depth + 1
                        )
                        visited.remove(neighbor_id)

            # Start DFS
            visited_set = {source_ent.id}
            dfs_recurse(
                curr_id=source_ent.id,
                curr_slug=source_ent.slug,
                path_nodes=[source_ent.slug],
                path_edges=[],
                visited=visited_set,
                curr_depth=0
            )

            # Record telemetry if limits hit
            telemetry_service.record_metric("traversal_depth_reached", depth_reached[0])
            if path_limit_hit[0]:
                telemetry_service.record_metric("traversal_path_limit_hit", True)

        else:
            raise ValueError(f"Invalid algorithm: {algorithm}. Must be 'bfs' or 'dfs'.")

        result = {
            "paths": paths
        }

        # 3. Cache the traversal result
        # Ensure we always add source and target to involved entities
        involved_entities.add(source)
        involved_entities.add(target)
        graph_cache.set_cached_traversal(
            query_prefix=query_prefix,
            result_data=result,
            involved_entities=list(involved_entities),
            involved_relationships=list(involved_relationships)
        )

        # Record duration metric
        duration = time.time() - start_time
        telemetry_service.record_metric("graph_traversal_duration_seconds", duration, {"algorithm": algorithm})

        return result

graph_traversal_service = GraphTraversalService()
