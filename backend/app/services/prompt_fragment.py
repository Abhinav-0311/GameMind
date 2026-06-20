import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from app.models.graph import WorldEntity, WorldEntityVersion, WorldRelationship
from app.repositories.graph_repository import graph_repo
from app.services.graph_cache import graph_cache
from app.services.telemetry import telemetry_service

logger = logging.getLogger("gamemind.prompt_fragment")

class PromptFragmentService:
    def get_or_create_entity_fragment(
        self, db: Session, slug: str, as_of: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get a cached entity prompt fragment, or compile a new one from SQL.
        """
        as_of_str = as_of.isoformat() if as_of else "current"
        fragment_id = f"entity:{slug}:{as_of_str}"
        
        # Check cache
        fragment, is_hit = graph_cache.get_cached_fragment(fragment_id)
        if is_hit:
            telemetry_service.record_metric("context_cache_hits_total", 1, {"type": "entity"})
            return fragment

        # Cache Miss
        telemetry_service.record_metric("context_cache_misses_total", 1, {"type": "entity"})
        telemetry_service.record_metric("context_fragment_rebuilds_total", 1, {"type": "entity"})

        entity = graph_repo.get_entity_by_slug(db, slug)
        if not entity:
            # Return a blank fragment for non-existent entities
            content = ""
            involved_keys = [f"graph:version:entity:{slug}"]
            stamps = graph_cache.get_stamps(involved_keys)
            comp_stamp = str(stamps[0])
            
            frag_result = {
                "fragment_id": fragment_id,
                "fragment_type": "entity",
                "version_stamp": comp_stamp,
                "source_entities": [slug],
                "content": content,
                "token_estimate": 0
            }
            graph_cache.set_cached_fragment(
                fragment_id=fragment_id,
                fragment_type="entity",
                version_stamp=comp_stamp,
                source_entities=[slug],
                content=content,
                token_estimate=0,
                involved_keys=involved_keys,
                stored_stamps=stamps
            )
            telemetry_service.record_metric("context_fragments_generated_total", 1, {"type": "entity"})
            return frag_result

        active_ver = graph_repo.get_active_entity_version(db, entity.id, as_of=as_of)
        
        if active_ver:
            content = (
                f"Entity: {active_ver.name} ({slug}) - "
                f"Type: {entity.entity_type} - "
                f"Info: {active_ver.description} "
                f"(Importance: {active_ver.importance_score})"
            )
        else:
            content = f"Entity: {slug} - Type: {entity.entity_type} (No active version attributes)"

        # Fetch current stamp of the entity
        involved_keys = [f"graph:version:entity:{slug}"]
        stamps = graph_cache.get_stamps(involved_keys)
        comp_stamp = str(stamps[0])
        token_est = (len(content) + 3) // 4  # Rough token approximation

        frag_result = {
            "fragment_id": fragment_id,
            "fragment_type": "entity",
            "version_stamp": comp_stamp,
            "source_entities": [slug],
            "content": content,
            "token_estimate": token_est
        }

        # Cache fragment
        graph_cache.set_cached_fragment(
            fragment_id=fragment_id,
            fragment_type="entity",
            version_stamp=comp_stamp,
            source_entities=[slug],
            content=content,
            token_estimate=token_est,
            involved_keys=involved_keys,
            stored_stamps=stamps
        )
        telemetry_service.record_metric("context_fragments_generated_total", 1, {"type": "entity"})
        return frag_result

    def get_or_create_relationship_fragment(
        self,
        db: Session,
        source_slug: str,
        target_slug: str,
        rel_type: str,
        rel_obj: WorldRelationship
    ) -> Dict[str, Any]:
        """
        Get a cached relationship prompt fragment, or compile a new one.
        """
        valid_from_str = rel_obj.valid_from.isoformat() if rel_obj.valid_from else "current"
        fragment_id = f"relationship:{source_slug}:{target_slug}:{rel_type}:{valid_from_str}"

        # Check cache
        fragment, is_hit = graph_cache.get_cached_fragment(fragment_id)
        if is_hit:
            telemetry_service.record_metric("context_cache_hits_total", 1, {"type": "relationship"})
            return fragment

        # Cache Miss
        telemetry_service.record_metric("context_cache_misses_total", 1, {"type": "relationship"})
        telemetry_service.record_metric("context_fragment_rebuilds_total", 1, {"type": "relationship"})

        # Format content
        props_str = str(rel_obj.properties) if rel_obj.properties else "{}"
        content = (
            f"Relationship: {source_slug} --({rel_type}, weight={rel_obj.weight})--> {target_slug} - "
            f"Details: {props_str}"
        )

        # Stamps involved: source, target, and relationship itself
        involved_keys = [
            f"graph:version:entity:{source_slug}",
            f"graph:version:entity:{target_slug}",
            f"graph:version:relationship:{source_slug}:{target_slug}:{rel_type}"
        ]
        stamps = graph_cache.get_stamps(involved_keys)
        comp_stamp = "-".join(str(s) for s in stamps)
        token_est = (len(content) + 3) // 4

        frag_result = {
            "fragment_id": fragment_id,
            "fragment_type": "relationship",
            "version_stamp": comp_stamp,
            "source_entities": [source_slug, target_slug],
            "content": content,
            "token_estimate": token_est
        }

        # Cache fragment
        graph_cache.set_cached_fragment(
            fragment_id=fragment_id,
            fragment_type="relationship",
            version_stamp=comp_stamp,
            source_entities=[source_slug, target_slug],
            content=content,
            token_estimate=token_est,
            involved_keys=involved_keys,
            stored_stamps=stamps
        )
        telemetry_service.record_metric("context_fragments_generated_total", 1, {"type": "relationship"})
        return frag_result

prompt_fragment_service = PromptFragmentService()
