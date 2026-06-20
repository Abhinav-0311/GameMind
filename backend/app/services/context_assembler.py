import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Set
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.models.graph import WorldRelationship, WorldEntity
from app.repositories.graph_repository import graph_repo
from app.services.prompt_fragment import prompt_fragment_service
from app.services.telemetry import telemetry_service

logger = logging.getLogger("gamemind.context_assembler")

class ContextAssemblerService:
    def assemble_context(
        self,
        db: Session,
        bfs_results: Optional[Dict[str, Any]] = None,
        dfs_results: Optional[Dict[str, Any]] = None,
        subgraph_results: Optional[Dict[str, Any]] = None,
        as_of: Optional[datetime] = None,
        token_budget: int = 1024
    ) -> str:
        """
        Assemble traversal paths and subgraph neighborhoods into a prompt-ready markdown block.
        Enforces a token budget with deterministic ranking and deduplication.
        """
        start_time = time.time()

        # 1. Identify involved entities and relationships
        bfs_entities: List[str] = []
        bfs_rels: List[Tuple[str, str, str]] = []
        if bfs_results and "paths" in bfs_results and bfs_results["paths"]:
            path = bfs_results["paths"][0]
            bfs_entities = path.get("nodes", [])
            for edge in path.get("edges", []):
                bfs_rels.append((edge["source"], edge["target"], edge["rel_type"]))

        dfs_entities: List[str] = []
        dfs_rels: List[Tuple[str, str, str]] = []
        if dfs_results and "paths" in dfs_results:
            for path in dfs_results["paths"]:
                dfs_entities.extend(path.get("nodes", []))
                for edge in path.get("edges", []):
                    dfs_rels.append((edge["source"], edge["target"], edge["rel_type"]))

        subgraph_entities: List[str] = []
        subgraph_rels: List[Tuple[str, str, str]] = []
        if subgraph_results:
            for node in subgraph_results.get("nodes", []):
                subgraph_entities.append(node["slug"])
            for edge in subgraph_results.get("edges", []):
                subgraph_rels.append((edge["source"], edge["target"], edge["rel_type"]))

        # Deduplicate entities and relationships
        all_unique_entities = list(set(bfs_entities + dfs_entities + subgraph_entities))
        all_unique_rels = list(set(bfs_rels + dfs_rels + subgraph_rels))

        # 2. Compile fragments (immutable retrieval from Cache/SQL)
        entity_fragments: Dict[str, Dict[str, Any]] = {}
        for slug in all_unique_entities:
            frag = prompt_fragment_service.get_or_create_entity_fragment(db, slug, as_of=as_of)
            if frag["content"]: # Only keep fragments with content
                entity_fragments[slug] = frag

        rel_fragments: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        for (src, tgt, rtype) in all_unique_rels:
            # Query the relationship object to pass to compiler
            source_ent = graph_repo.get_entity_by_slug(db, src)
            target_ent = graph_repo.get_entity_by_slug(db, tgt)
            if source_ent and target_ent:
                query = db.query(WorldRelationship).filter(
                    WorldRelationship.source_id == source_ent.id,
                    WorldRelationship.target_id == target_ent.id,
                    WorldRelationship.rel_type == rtype
                )
                if as_of:
                    query = query.filter(
                        and_(
                            WorldRelationship.valid_from <= as_of,
                            or_(
                                WorldRelationship.valid_to.is_(None),
                                WorldRelationship.valid_to > as_of
                            )
                        )
                    )
                else:
                    query = query.filter(WorldRelationship.valid_to.is_(None))
                
                rel_obj = query.first()
                if rel_obj:
                    frag = prompt_fragment_service.get_or_create_relationship_fragment(
                        db=db,
                        source_slug=src,
                        target_slug=tgt,
                        rel_type=rtype,
                        rel_obj=rel_obj
                    )
                    rel_fragments[(src, tgt, rtype)] = frag

        # 3. Deterministic Ranking
        # We will build a list of tuples: (priority, score, identifier, fragment_dict)
        # Priority rules:
        # 1: BFS entities (in path order)
        # 2: BFS relationships (in path order)
        # 3: Subgraph entities (ranked by importance score desc, alphabetically by slug for tie break)
        # 4: Subgraph / DFS relationships (alphabetically by source:target:type)
        ranked_items = []

        # Track processed items to avoid adding them to lower priority categories
        processed_entities: Set[str] = set()
        processed_rels: Set[Tuple[str, str, str]] = set()

        # BFS Priority
        for idx, slug in enumerate(bfs_entities):
            if slug in entity_fragments and slug not in processed_entities:
                ranked_items.append((1, idx, slug, entity_fragments[slug]))
                processed_entities.add(slug)
        for idx, edge in enumerate(bfs_rels):
            if edge in rel_fragments and edge not in processed_rels:
                edge_str = f"{edge[0]}:{edge[1]}:{edge[2]}"
                ranked_items.append((2, idx, edge_str, rel_fragments[edge]))
                processed_rels.add(edge)

        # Subgraph / DFS Entities Priority
        subgraph_entity_candidates = []
        for slug in all_unique_entities:
            if slug in entity_fragments and slug not in processed_entities:
                frag = entity_fragments[slug]
                importance = frag.get("token_estimate", 0) # default fallback
                # Fetch actual importance from DB if possible or metadata
                entity_obj = graph_repo.get_entity_by_slug(db, slug)
                active_ver = graph_repo.get_active_entity_version(db, entity_obj.id, as_of=as_of) if entity_obj else None
                importance_score = active_ver.importance_score if active_ver else 0
                subgraph_entity_candidates.append((-importance_score, slug, frag))

        # Sort subgraph entities by importance score desc, then slug asc
        subgraph_entity_candidates.sort(key=lambda x: (x[0], x[1]))
        for rank_idx, (neg_score, slug, frag) in enumerate(subgraph_entity_candidates):
            ranked_items.append((3, rank_idx, slug, frag))
            processed_entities.add(slug)

        # Subgraph / DFS Relationships Priority
        subgraph_rel_candidates = []
        for edge in all_unique_rels:
            if edge in rel_fragments and edge not in processed_rels:
                edge_str = f"{edge[0]}:{edge[1]}:{edge[2]}"
                subgraph_rel_candidates.append((edge_str, rel_fragments[edge]))

        # Sort relationships alphabetically
        subgraph_rel_candidates.sort(key=lambda x: x[0])
        for rank_idx, (edge_str, frag) in enumerate(subgraph_rel_candidates):
            ranked_items.append((4, rank_idx, edge_str, frag))
            # We don't strictly need to add to processed_rels since we are at end

        # 4. Token Budget Enforcement & Clipping
        compiled_fragments: List[str] = []
        current_tokens = 0
        truncated = False

        for priority, score, identifier, frag in ranked_items:
            token_est = frag["token_estimate"]
            if current_tokens + token_est <= token_budget:
                compiled_fragments.append(frag["content"])
                current_tokens += token_est
            else:
                truncated = True
                # Break to enforce deterministic truncation on budget overflow
                break

        # Append Warning if truncated
        if truncated:
            warning = "[Context Truncated: Token Budget Exceeded]"
            # Only append if we have budget room or at least some content
            compiled_fragments.append(warning)

        # 5. Format Final Output
        if compiled_fragments:
            final_content = "\n".join(compiled_fragments)
            final_context = f"[World Graph Lore Context]\n{final_content}"
        else:
            final_context = ""

        # Record Telemetry Metrics after assembly completes
        duration = time.time() - start_time
        telemetry_service.record_metric("context_assembly_duration_seconds", duration)

        return final_context

context_assembler_service = ContextAssemblerService()
