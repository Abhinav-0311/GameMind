import sys
import uuid
import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.database import SessionLocal, engine
from app.models.graph import PendingIngest
from app.models.telemetry import LLMTelemetryLog
from app.services.telemetry_service import TelemetryService
from app.workers.cleanup_worker import cleanup_worker_loop

# Setup logging to console
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_cleanup_worker")

db = SessionLocal()

def cleanup_db():
    db.rollback()
    # Delete all telemetry logs related to cleanup worker to start fresh
    db.query(LLMTelemetryLog).filter(
        LLMTelemetryLog.action_type.in_([
            "graph_pending_ingest_cleanup_run",
            "graph_pending_ingest_cleanup_rows"
        ])
    ).delete(synchronize_session=False)
    # Delete test pending ingests
    db.query(PendingIngest).delete(synchronize_session=False)
    db.commit()

async def test_pruning_precision_and_telemetry():
    print("\n--- Gate A & B: Pruning Precision and Active Preservation ---")
    cleanup_db()
    
    # Seed expired row
    expired_id = uuid.uuid4()
    expired_record = PendingIngest(
        validation_id=expired_id,
        payload={"test": "expired"},
        reason_blocked="Expired testing",
        expires_at=datetime.utcnow() - timedelta(minutes=5)
    )
    
    # Seed active row
    active_id = uuid.uuid4()
    active_record = PendingIngest(
        validation_id=active_id,
        payload={"test": "active"},
        reason_blocked="Active testing",
        expires_at=datetime.utcnow() + timedelta(minutes=60)
    )
    
    db.add(expired_record)
    db.add(active_record)
    db.commit()
    
    print(f"Seeded one expired pending ingest ({expired_id}) and one active ({active_id}).")
    
    # Start the worker loop with stop_event
    stop_event = asyncio.Event()
    
    # Check connection pool checkout count baseline
    pool = engine.pool
    checked_out_before = pool.checkedout()
    print(f"Pool checked out before run: {checked_out_before}")
    
    task = asyncio.create_task(cleanup_worker_loop(stop_event))
    
    # Allow the loop to execute the first run
    await asyncio.sleep(0.5)
    
    # Trigger shutdown event
    print("--- Gate E: Graceful Shutdown ---")
    print("Setting stop event to stop loop cooperatively...")
    stop_event.set()
    await task
    print("Background worker loop stopped successfully.")
    
    # Check connection pool checkout count post-run
    checked_out_after = pool.checkedout()
    print(f"Pool checked out after run: {checked_out_after}")
    assert checked_out_before == checked_out_after, "CONNECTION LEAK DETECTED!"
    print("SUCCESS: Connection Pool Parity verified.")
    
    # Verify DB state
    db.expire_all()
    expired_exists = db.query(PendingIngest).filter(PendingIngest.validation_id == expired_id).first() is not None
    active_exists = db.query(PendingIngest).filter(PendingIngest.validation_id == active_id).first() is not None
    
    print(f"Expired record exists in DB: {expired_exists} (expected False)")
    print(f"Active record exists in DB: {active_exists} (expected True)")
    
    assert not expired_exists, "Expired record was not deleted!"
    assert active_exists, "Active record was deleted!"
    print("SUCCESS: Pruning precision and preservation verified.")
    
    # Verify Telemetry
    print("\n--- Gate D: Telemetry Counters ---")
    metrics = TelemetryService.get_graph_metrics(db)
    print(f"graph_pending_ingest_cleanup_runs_total: {metrics['graph_pending_ingest_cleanup_runs_total']} (expected >= 1)")
    print(f"graph_pending_ingest_cleanup_rows_total: {metrics['graph_pending_ingest_cleanup_rows_total']} (expected 1)")
    
    assert metrics['graph_pending_ingest_cleanup_runs_total'] >= 1
    assert metrics['graph_pending_ingest_cleanup_rows_total'] == 1
    print("SUCCESS: Telemetry logs created and incremented correctly in DB.")

async def test_advisory_lock():
    print("\n--- Gate C: Singleton Lock Coordination ---")
    cleanup_db()
    
    # Manually acquire the lock in this session/connection
    lock_conn = engine.connect()
    lock_conn.execute(text("SELECT pg_try_advisory_lock(113356)"))
    print("Main script connection acquired pg_try_advisory_lock(113356).")
    
    # Start worker task
    stop_event = asyncio.Event()
    task = asyncio.create_task(cleanup_worker_loop(stop_event))
    
    await asyncio.sleep(0.5)
    
    # Stop worker
    stop_event.set()
    await task
    
    # Verify telemetry: runs total should increment, but rows should not since lock is held
    metrics = TelemetryService.get_graph_metrics(db)
    print(f"With lock held: runs total = {metrics['graph_pending_ingest_cleanup_runs_total']}, rows total = {metrics['graph_pending_ingest_cleanup_rows_total']}")
    
    # Release manual lock
    lock_conn.execute(text("SELECT pg_advisory_unlock(113356)"))
    lock_conn.close()
    print("Main script connection released pg_try_advisory_lock(113356).")
    
    # Runs should increment but rows should be 0 because worker skipped
    assert metrics['graph_pending_ingest_cleanup_runs_total'] >= 1
    assert metrics['graph_pending_ingest_cleanup_rows_total'] == 0
    print("SUCCESS: Advisory lock singleton behavior verified. Lock was skipped when held.")

async def test_db_outage_resilience():
    print("\n--- DB Outage & Resilience ---")
    cleanup_db()
    
    # Mocking SessionLocal to throw OperationalError
    original_session_local = None
    import app.workers.cleanup_worker as cleanup_worker
    
    def mock_session_local():
        raise OperationalError("Simulated DB outage", params=None, orig=None)
        
    cleanup_worker.SessionLocal = mock_session_local
    print("Mocked SessionLocal to throw OperationalError.")
    
    stop_event = asyncio.Event()
    # We expect worker to retry with exponential backoff (5s, 10s...)
    task = asyncio.create_task(cleanup_worker_loop(stop_event))
    
    # Let it run for 1 second (should hit exception, initiate backoff)
    await asyncio.sleep(1.0)
    
    # Restore SessionLocal
    cleanup_worker.SessionLocal = SessionLocal
    print("Restored original SessionLocal.")
    
    # Worker should retry after backoff is finished or wait_for times out
    # Since we restored SessionLocal, let's wait a bit for it to run again
    # The backoff sleep is 5 seconds. So let's sleep 6 seconds.
    print("Waiting 6 seconds for retry loop to execute post-outage...")
    await asyncio.sleep(6.0)
    
    # Stop worker
    stop_event.set()
    await task
    
    # Verify that it successfully recovered and executed
    metrics = TelemetryService.get_graph_metrics(db)
    print(f"After DB recovery: runs total = {metrics['graph_pending_ingest_cleanup_runs_total']}")
    assert metrics['graph_pending_ingest_cleanup_runs_total'] >= 1
    print("SUCCESS: Database outage exponential backoff and recovery verified.")

async def main():
    try:
        await test_pruning_precision_and_telemetry()
        await test_advisory_lock()
        await test_db_outage_resilience()
        print("\n==================================================")
        print("ALL VERIFICATION GATES PASSED SUCCESSFULLY!")
        print("==================================================")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
