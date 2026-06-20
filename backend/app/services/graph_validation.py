import uuid
import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from app.repositories.graph_repository import GraphRepository
from app.models.graph import (
    WorldEntity,
    WorldEntityVersion,
    WorldRelationship,
    RelationshipTypeRule,
    PendingIngest,
    ConsistencyOverride
)

class ValidationError(Exception):
    """Exception raised when deterministic validation fails, containing the pending ingest reference."""
    def __init__(self, validation_id: uuid.UUID, message: str):
        super().__init__(message)
        self.validation_id = validation_id
        self.message = message


class GraphValidationService:
    """
    Service layer orchestrating Stage 1 deterministic validation, transaction boundary control,
    and override auditing workflows.
    """
    def __init__(self, db: Session):
        self.db = db
        self.repo = GraphRepository(db)

    def _lock_endpoints_ordered(self, source_slug: str, target_slug: str) -> dict:
        """
        Helper method enforcing Service-Owned Lock Ordering. Locks the version rows
        of the source and target nodes in lexicographical (alphabetical) order of their slugs.
        """
        self.repo._lock_entities_ordered([source_slug, target_slug])
        
        # Populate returned dictionary for backward compatibility with existing callers/tests
        locked_versions = {}
        for slug in [source_slug, target_slug]:
            entity, active_ver = self.repo.get_active_entity_by_slug(slug)
            if entity and active_ver:
                locked_versions[slug] = active_ver
        return locked_versions

    def validate_and_create_entity(
        self,
        slug: str,
        entity_type: str,
        name: str,
        description: str,
        importance_score: int = 0,
        properties: dict = None
    ) -> WorldEntity:
        """
        Validates entity parameters, checking for active duplicate slugs,
        and creates the entity inside a committed transaction.
        """
        if properties is None:
            properties = {}

        try:
            # 1. Deterministic Validation: Duplicate active slug check
            entity, active_ver = self.repo.get_active_entity_by_slug(slug)
            if active_ver:
                raise ValueError(f"Entity slug '{slug}' is already in use by an active node")

            # 2. Deterministic Validation: Basic name and description checks
            if not name.strip():
                raise ValueError("Entity name cannot be empty")
            if not description.strip():
                raise ValueError("Entity description cannot be empty")

            # 3. Create using repository
            new_entity = self.repo.create_entity(
                slug=slug,
                entity_type=entity_type,
                name=name,
                description=description,
                importance_score=importance_score,
                properties=properties
            )
            self.db.commit() # Commit transaction
            
            try:
                from app.services.telemetry_service import TelemetryService
                TelemetryService.record_graph_entity_create(self.db, slug, entity_type)
            except Exception as tel_err:
                print(f"Telemetry failed: {tel_err}")
                
            return new_entity

        except Exception as e:
            self.db.rollback() # Rollback active failed transaction block
            # Store payload in pending ingests
            validation_id = self._store_pending_ingest(
                payload={
                    "operation": "create_entity",
                    "slug": slug,
                    "entity_type": entity_type,
                    "name": name,
                    "description": description,
                    "importance_score": importance_score,
                    "properties": properties
                },
                reason_blocked=str(e)
            )
            
            try:
                from app.services.telemetry_service import TelemetryService
                TelemetryService.record_graph_validation_failure(self.db, "create_entity", str(e))
            except Exception as tel_err:
                print(f"Telemetry failed: {tel_err}")
                
            raise ValidationError(validation_id, f"Entity validation failed: {str(e)}")

    def validate_and_create_relationship(
        self,
        source_slug: str,
        target_slug: str,
        rel_type: str,
        weight: float = 1.0,
        properties: dict = None
    ) -> WorldRelationship:
        """
        Performs taxonomy registry validation, endpoint active state check,
        and duplicate active relationship checks under lexicographical row-level locks.
        """
        if properties is None:
            properties = {}

        try:
            # 1. Service-owned deterministic lock ordering to prevent deadlocks
            self._lock_endpoints_ordered(source_slug, target_slug)

            source, source_active = self.repo.get_active_entity_by_slug(source_slug)
            target, target_active = self.repo.get_active_entity_by_slug(target_slug)

            # 2. Active endpoint validation
            if not source_active or not target_active:
                raise ValueError(
                    f"Relationship endpoints must be active. "
                    f"source active: {source_active is not None}, "
                    f"target active: {target_active is not None}"
                )

            # 3. Taxonomy Registry check
            rule = self.db.query(RelationshipTypeRule).filter(
                RelationshipTypeRule.rel_type == rel_type,
                RelationshipTypeRule.allowed_source_type == source.entity_type,
                RelationshipTypeRule.allowed_target_type == target.entity_type
            ).first()

            if not rule:
                raise ValueError(
                    f"Relationship taxonomy violation: Edge type '{rel_type}' is not "
                    f"permitted from '{source.entity_type}' to '{target.entity_type}'"
                )

            # 4. Duplicate active relationship check
            active_rel = self.repo.get_active_relationship(self.db, source_slug, target_slug, rel_type)
            if active_rel:
                raise ValueError(
                    f"Active relationship of type '{rel_type}' already exists "
                    f"between '{source_slug}' and '{target_slug}'"
                )

            # 4b. Contradiction check
            from app.services.contradiction_engine import contradiction_engine
            is_contradict, reason = contradiction_engine.check_contradiction(self.db, source_slug, target_slug, rel_type)
            if is_contradict:
                raise ValueError(reason)

            # 5. Create edge
            new_rel = self.repo.create_relationship(
                source_slug=source_slug,
                target_slug=target_slug,
                rel_type=rel_type,
                weight=weight,
                properties=properties
            )
            self.db.commit()
            
            try:
                from app.services.telemetry_service import TelemetryService
                TelemetryService.record_graph_relationship_create(self.db, source_slug, target_slug, rel_type)
            except Exception as tel_err:
                print(f"Telemetry failed: {tel_err}")
                
            return new_rel

        except Exception as e:
            self.db.rollback()
            validation_id = self._store_pending_ingest(
                payload={
                    "operation": "create_relationship",
                    "source_slug": source_slug,
                    "target_slug": target_slug,
                    "rel_type": rel_type,
                    "weight": weight,
                    "properties": properties
                },
                reason_blocked=str(e)
            )
            
            try:
                from app.services.telemetry_service import TelemetryService
                TelemetryService.record_graph_validation_failure(self.db, "create_relationship", str(e))
            except Exception as tel_err:
                print(f"Telemetry failed: {tel_err}")
                
            raise ValidationError(validation_id, f"Relationship validation failed: {str(e)}")

    def _store_pending_ingest(self, payload: dict, reason_blocked: str) -> uuid.UUID:
        """
        Stores the failed payload in the pending_ingests store table.
        Operates inside a separate transaction block to ensure persistence.
        """
        validation_id = uuid.uuid4()
        pending = PendingIngest(
            validation_id=validation_id,
            payload=payload,
            reason_blocked=reason_blocked,
            created_at=func.now(),
            expires_at=func.now() + datetime.timedelta(hours=1)
        )
        # Create a new local transaction to persist the pending record
        self.db.begin_nested() # Nested transaction (savepoint)
        self.db.add(pending)
        self.db.commit()
        return validation_id

    def apply_override(
        self,
        validation_id: uuid.UUID,
        applied_by: str,
        reason: str
    ) -> bool:
        """
        Bypasses deterministic validators, applies the pending payload directly,
        logs the administrative audit trail, and deletes the pending ingest record.
        """
        pending = self.db.query(PendingIngest).filter(
            PendingIngest.validation_id == validation_id
        ).with_for_update().first()

        if not pending:
            raise ValueError(f"No pending ingest payload found with ID '{validation_id}'")

        payload = pending.payload
        operation = payload.get("operation")

        if operation == "create_entity":
            # Direct repository bypass of validators
            self.repo.create_entity(
                slug=payload["slug"],
                entity_type=payload["entity_type"],
                name=payload["name"],
                description=payload["description"],
                importance_score=payload["importance_score"],
                properties=payload["properties"]
            )
        elif operation == "create_relationship":
            # Direct repository bypass of validators
            self.repo.create_relationship(
                source_slug=payload["source_slug"],
                target_slug=payload["target_slug"],
                rel_type=payload["rel_type"],
                weight=payload["weight"],
                properties=payload["properties"]
            )
        else:
            raise ValueError(f"Unsupported pending ingest operation: '{operation}'")

        # Log override audit trail
        override = ConsistencyOverride(
            id=uuid.uuid4(),
            validation_id=validation_id,
            blocked_payload=pending.payload,
            reason_blocked=pending.reason_blocked,
            override_applied_by=applied_by,
            override_reason=reason,
            override_timestamp=func.now()
        )
        self.db.add(override)

        # Delete the pending ingest record from queue
        self.db.delete(pending)
        self.db.commit()
        
        try:
            from app.services.telemetry_service import TelemetryService
            TelemetryService.record_graph_override(self.db, validation_id, applied_by)
        except Exception as tel_err:
            print(f"Telemetry failed: {tel_err}")
            
        return True

    def validate_transition(
        self,
        entity_type: str,
        current_properties: dict,
        next_properties: dict
    ) -> bool:
        """
        Hook executing state transition validations (e.g. quest progress flow checks).
        """
        if entity_type == "Quest":
            current_status = current_properties.get("status", "inactive")
            next_status = next_properties.get("status", "inactive")
            
            # Block transitions bypassing active state
            if current_status == "inactive" and next_status == "completed":
                raise ValueError("Quests cannot transition directly from inactive to completed")
                
        return True
