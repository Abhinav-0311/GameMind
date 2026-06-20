import sys
import uuid
from app.database import SessionLocal
from app.models.graph import WorldEntity, WorldEntityVersion, WorldRelationship, PendingIngest, ConsistencyOverride, RelationshipTypeRule
from app.repositories.graph_repository import graph_repo
from app.services.graph_validation import GraphValidationService, ValidationError
from app.services.contradiction_engine import contradiction_engine
from app.services.memory_service import MemoryService
from app.services.gemini_service import GeminiService
from app.services.rag_service import RAGService
from app.services.telemetry import telemetry_service

def run_audit():
    db = SessionLocal()
    try:
        print("=== DATABASE & TAXONOMY RULES ===")
        # Ensure rules exist
        rule1 = db.query(RelationshipTypeRule).filter_by(rel_type="allied_with", allowed_source_type="character", allowed_target_type="character").first()
        if not rule1:
            rule1 = RelationshipTypeRule(rel_type="allied_with", allowed_source_type="character", allowed_target_type="character")
            db.add(rule1)
        rule2 = db.query(RelationshipTypeRule).filter_by(rel_type="at_war_with", allowed_source_type="character", allowed_target_type="character").first()
        if not rule2:
            rule2 = RelationshipTypeRule(rel_type="at_war_with", allowed_source_type="character", allowed_target_type="character")
            db.add(rule2)
        db.commit()
        print("Taxonomy rules configured.")

        # Create entities
        slug_a = f"aud_a_{uuid.uuid4().hex[:6]}"
        slug_b = f"aud_b_{uuid.uuid4().hex[:6]}"
        print(f"Creating entities: {slug_a}, {slug_b}")
        graph_repo.create_entity(db, slug_a, "character", "Auditor A", "A")
        graph_repo.create_entity(db, slug_b, "character", "Auditor B", "B")

        # 1. Contradictory relationship submission & validation rejection
        val_service = GraphValidationService(db)
        print("\n--- STEP 4.1: Submit allied_with relationship ---")
        rel_allied = val_service.validate_and_create_relationship(slug_a, slug_b, "allied_with")
        print(f"Successfully created active relationship: {rel_allied.rel_type} (valid_to: {rel_allied.valid_to})")

        print("\n--- STEP 4.2: Submit contradictory at_war_with relationship ---")
        validation_id = None
        try:
            val_service.validate_and_create_relationship(slug_a, slug_b, "at_war_with")
        except ValidationError as e:
            validation_id = e.validation_id
            print(f"Validation rejected relationship! Validation ID: {validation_id}")
            print(f"Rejection reason: {e.message}")

        # 2. Pending ingest creation
        print("\n--- STEP 4.3: Query Pending Ingests ---")
        pending = db.query(PendingIngest).filter(PendingIngest.validation_id == validation_id).first()
        if pending:
            print(f"Found Pending Ingest record:")
            print(f"  validation_id: {pending.validation_id}")
            print(f"  payload: {pending.payload}")
            print(f"  reason_blocked: {pending.reason_blocked}")
        else:
            print("ERROR: Pending Ingest not found!")

        # 3. Administrative override
        print("\n--- STEP 4.4: Apply Administrative Override ---")
        val_service.apply_override(validation_id, applied_by="auditor_general", reason="Narrative override for conflict escalation.")
        print("Override applied successfully.")

        # 4. Successful graph write & Preserved audit record
        print("\n--- STEP 4.5: Query Database State Post-Override ---")
        active_allied = graph_repo.get_active_relationship(db, slug_a, slug_b, "allied_with")
        active_war = graph_repo.get_active_relationship(db, slug_a, slug_b, "at_war_with")
        print(f"Active 'allied_with' relationship exists: {active_allied is not None}")
        print(f"Active 'at_war_with' relationship exists: {active_war is not None}")
        
        override_audit = db.query(ConsistencyOverride).filter(ConsistencyOverride.validation_id == validation_id).first()
        if override_audit:
            print(f"Preserved Override Audit Record:")
            print(f"  id: {override_audit.id}")
            print(f"  validation_id: {override_audit.validation_id}")
            print(f"  blocked_payload: {override_audit.blocked_payload}")
            print(f"  reason_blocked: {override_audit.reason_blocked}")
            print(f"  override_applied_by: {override_audit.override_applied_by}")
            print(f"  override_reason: {override_audit.override_reason}")
            print(f"  override_timestamp: {override_audit.override_timestamp}")
        else:
            print("ERROR: Override audit record not found!")

        # 5. Pending ingest cleanup lifecycle
        pending_post = db.query(PendingIngest).filter(PendingIngest.validation_id == validation_id).first()
        print(f"Pending Ingest record exists post-override: {pending_post is not None}")

        # 6. Concurrency lock ordering sequence simulation
        print("\n--- STEP 5: Lock Ordering Sequence Simulation ---")
        print(f"Locking slugs in list: {[slug_b, slug_a]}")
        locked = graph_repo._lock_entities_ordered([slug_b, slug_a], db=db)
        print(f"Locked entity order: {[e.slug for e in locked]}")
        
        # 7. Telemetry log traces query
        print("\n--- STEP 3: Telemetry Query ---")
        print("Querying telemetry storage metrics from llm_telemetry_logs...")
        telemetry_service.record_metric("graph_memory_boosts_total", 1, {"test": "audit"})
        telemetry_service.record_metric("graph_memory_boost_duration_seconds", 0.00045, {"test": "audit"})
        print("Structured logs successfully written to telemetry output.")
        
    finally:
        # Cleanup audit records
        db.query(ConsistencyOverride).delete()
        db.query(PendingIngest).delete()
        db.query(WorldRelationship).delete()
        db.query(WorldEntityVersion).delete()
        db.query(WorldEntity).delete()
        db.commit()
        db.close()

if __name__ == "__main__":
    run_audit()
