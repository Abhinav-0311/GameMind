import logging
from typing import Dict, Set, List, Tuple, Optional
from sqlalchemy.orm import Session
from app.models.graph import WorldRelationship, WorldEntity
from app.repositories.graph_repository import graph_repo

logger = logging.getLogger("gamemind.contradiction_engine")

class ContradictionEngineService:
    def __init__(self):
        # Configurable conflicting relationship sets
        self._conflict_sets: List[Set[str]] = [
            {"allied_with", "at_war_with"},
            {"owns", "destroyed_by"},
            {"located_in", "exiled_from"}
        ]

    def add_conflict_rule(self, rel_type_a: str, rel_type_b: str) -> None:
        """Allow dynamic configuration of conflict rules."""
        for cset in self._conflict_sets:
            if rel_type_a in cset or rel_type_b in cset:
                cset.add(rel_type_a)
                cset.add(rel_type_b)
                return
        self._conflict_sets.append({rel_type_a, rel_type_b})

    def get_conflicting_types(self, rel_type: str) -> Set[str]:
        """Get all relationship types that conflict with the given type."""
        conflicts = set()
        for cset in self._conflict_sets:
            if rel_type in cset:
                conflicts.update(cset)
        if rel_type in conflicts:
            conflicts.remove(rel_type)
        return conflicts

    def check_contradiction(
        self,
        db: Session,
        source_slug: str,
        target_slug: str,
        rel_type: str,
        game_project_id: str = "default_project"
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if adding/updating a relationship of rel_type between source and target
        violates any contradiction rules with existing ACTIVE relationships.
        Historical relationships (valid_to is not null) are ignored.
        """
        conflicting_types = self.get_conflicting_types(rel_type)
        if not conflicting_types:
            return False, None

        source_entity = graph_repo.get_entity_by_slug(db, source_slug, game_project_id=game_project_id)
        target_entity = graph_repo.get_entity_by_slug(db, target_slug, game_project_id=game_project_id)
        if not source_entity or not target_entity:
            return False, None

        # Check for active relationships between these two endpoints of conflicting types in both directions
        active_rels = db.query(WorldRelationship).filter(
            WorldRelationship.valid_to.is_(None),
            WorldRelationship.rel_type.in_(conflicting_types),
            (
                ((WorldRelationship.source_id == source_entity.id) & (WorldRelationship.target_id == target_entity.id)) |
                ((WorldRelationship.source_id == target_entity.id) & (WorldRelationship.target_id == source_entity.id))
            )
        ).all()

        if active_rels:
            conflict = active_rels[0]
            # Fetch slugs of source/target of conflict relationship
            conflict_source = db.query(WorldEntity).filter(
                WorldEntity.id == conflict.source_id,
                WorldEntity.game_project_id == game_project_id
            ).first()
            conflict_target = db.query(WorldEntity).filter(
                WorldEntity.id == conflict.target_id,
                WorldEntity.game_project_id == game_project_id
            ).first()
            conflict_src_slug = conflict_source.slug if conflict_source else "unknown"
            conflict_tgt_slug = conflict_target.slug if conflict_target else "unknown"
            
            reason = (
                f"Contradiction detected: proposed relationship '{rel_type}' between "
                f"'{source_slug}' and '{target_slug}' conflicts with active relationship "
                f"'{conflict.rel_type}' between '{conflict_src_slug}' and '{conflict_tgt_slug}'."
            )
            return True, reason

        return False, None

contradiction_engine = ContradictionEngineService()
