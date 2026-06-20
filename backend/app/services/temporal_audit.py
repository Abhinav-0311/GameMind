import logging
from datetime import datetime
from typing import Dict, Any, List
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
from app.models.graph import WorldEntity, WorldEntityVersion, WorldRelationship
from app.services.telemetry_service import TelemetryService

logger = logging.getLogger("gamemind.temporal_audit")

class TemporalNarrativeAuditor:
    @staticmethod
    def audit_state_drift(db: Session, timestamp_a: datetime, timestamp_b: datetime) -> Dict[str, Any]:
        """
        Reconstructs the difference between timestamp_a and timestamp_b.
        Returns a diff-oriented payload:
        {
          "entities_added": [...],
          "entities_removed": [...],
          "relationships_added": [...],
          "relationships_removed": [...],
          "relationships_changed": [...]
        }
        """
        # Ensure timezone-aware comparisons
        import datetime as dt_mod
        if timestamp_a.tzinfo is None:
            timestamp_a = timestamp_a.replace(tzinfo=dt_mod.timezone.utc)
        if timestamp_b.tzinfo is None:
            timestamp_b = timestamp_b.replace(tzinfo=dt_mod.timezone.utc)

        # Ensure timestamp_a is before timestamp_b
        if timestamp_a > timestamp_b:
            timestamp_a, timestamp_b = timestamp_b, timestamp_a

        # Record temporal audit in telemetry
        TelemetryService.record_narrative_metric(
            db,
            action_type="temporal_audits_total",
            npc_slug="system",
            model_used="temporal_auditor",
            error_str=None
        )

        # ----------------------------------------------------
        # 1. Entity Audits
        # ----------------------------------------------------
        entities_added: List[str] = []
        entities_removed: List[str] = []

        # Find entity versions created in the interval where version == 1
        added_versions = db.query(WorldEntityVersion).join(WorldEntity).filter(
            WorldEntityVersion.valid_from >= timestamp_a,
            WorldEntityVersion.valid_from <= timestamp_b,
            WorldEntityVersion.version == 1
        ).all()
        for ver in added_versions:
            entities_added.append(ver.entity.slug)

        # Find entities retired (soft-deleted) in the interval
        # An entity is retired if its active version valid_to was set to a timestamp in the interval
        removed_versions = db.query(WorldEntityVersion).join(WorldEntity).filter(
            WorldEntityVersion.valid_to >= timestamp_a,
            WorldEntityVersion.valid_to <= timestamp_b
        ).all()
        
        # Verify if there is any active version for these entities after timestamp_b
        for ver in removed_versions:
            # Check if there is a newer active version or version valid_from > ver.valid_to
            newer_ver = db.query(WorldEntityVersion).filter(
                WorldEntityVersion.entity_id == ver.entity_id,
                WorldEntityVersion.valid_from > ver.valid_to
            ).first()
            if not newer_ver and ver.entity.slug not in entities_removed:
                entities_removed.append(ver.entity.slug)

        # ----------------------------------------------------
        # 2. Relationship Audits
        # ----------------------------------------------------
        relationships_added: List[Dict[str, Any]] = []
        relationships_removed: List[Dict[str, Any]] = []
        relationships_changed: List[Dict[str, Any]] = []

        # Find relationships created in the interval where version == 1
        added_rels = db.query(WorldRelationship).filter(
            WorldRelationship.valid_from >= timestamp_a,
            WorldRelationship.valid_from <= timestamp_b,
            WorldRelationship.version == 1
        ).all()

        for rel in added_rels:
            src = db.query(WorldEntity).filter(WorldEntity.id == rel.source_id).first()
            tgt = db.query(WorldEntity).filter(WorldEntity.id == rel.target_id).first()
            if src and tgt:
                relationships_added.append({
                    "source": src.slug,
                    "target": tgt.slug,
                    "type": rel.rel_type,
                    "weight": rel.weight
                })

        # Find relationships retired (soft-deleted) in the interval
        removed_rels = db.query(WorldRelationship).filter(
            WorldRelationship.valid_to >= timestamp_a,
            WorldRelationship.valid_to <= timestamp_b
        ).all()

        for rel in removed_rels:
            # Verify if there is a newer version of the same relationship type between same endpoints
            newer_rel = db.query(WorldRelationship).filter(
                WorldRelationship.source_id == rel.source_id,
                WorldRelationship.target_id == rel.target_id,
                WorldRelationship.rel_type == rel.rel_type,
                WorldRelationship.valid_from > rel.valid_to
            ).first()

            src = db.query(WorldEntity).filter(WorldEntity.id == rel.source_id).first()
            tgt = db.query(WorldEntity).filter(WorldEntity.id == rel.target_id).first()
            if not newer_rel and src and tgt:
                relationships_removed.append({
                    "source": src.slug,
                    "target": tgt.slug,
                    "type": rel.rel_type
                })

        # Find relationships changed in the interval (version > 1 created in interval)
        changed_rels = db.query(WorldRelationship).filter(
            WorldRelationship.valid_from >= timestamp_a,
            WorldRelationship.valid_from <= timestamp_b,
            WorldRelationship.version > 1
        ).all()

        for rel in changed_rels:
            # Fetch the previous version of this relationship to see old weight/properties
            prev_rel = db.query(WorldRelationship).filter(
                WorldRelationship.source_id == rel.source_id,
                WorldRelationship.target_id == rel.target_id,
                WorldRelationship.rel_type == rel.rel_type,
                WorldRelationship.version == rel.version - 1
            ).first()

            src = db.query(WorldEntity).filter(WorldEntity.id == rel.source_id).first()
            tgt = db.query(WorldEntity).filter(WorldEntity.id == rel.target_id).first()
            
            if src and tgt:
                old_weight = prev_rel.weight if prev_rel else 0.0
                relationships_changed.append({
                    "source": src.slug,
                    "target": tgt.slug,
                    "type": rel.rel_type,
                    "property": "weight",
                    "old_value": old_weight,
                    "new_value": rel.weight
                })

        return {
            "entities_added": entities_added,
            "entities_removed": entities_removed,
            "relationships_added": relationships_added,
            "relationships_removed": relationships_removed,
            "relationships_changed": relationships_changed
        }
