import asyncio
import logging
from sqlalchemy.sql import text
from sqlalchemy.exc import DBAPIError, OperationalError
from app.database import SessionLocal
from app.services.telemetry_service import TelemetryService

logger = logging.getLogger("gamemind.cleanup_worker")

async def cleanup_worker_loop(stop_event: asyncio.Event):
    """
    Background worker loop that prunes expired pending ingests.
    Runs every 5 minutes (300 seconds), serialized via pg_try_advisory_lock(113356).
    Responsive to stop_event for clean shutdown and resilient with exponential backoff on DB failure.
    """
    logger.info("Pending Ingest Cleanup Worker background loop started.")
    
    db_fail_delay = 5.0
    
    while not stop_event.is_set():
        logger.info("Cleanup cycle run started.")
        
        # Increment runs telemetry
        db = None
        try:
            db = SessionLocal()
            TelemetryService.record_graph_pending_ingest_cleanup_run(db)
        except Exception as e:
            logger.error(f"Failed to record cleanup run telemetry: {e}")
        finally:
            if db:
                db.close()
            
        # Execute the database prune logic
        lock_acquired = False
        db = None
        checked_out_before = 0
        pool = None
        
        try:
            db = SessionLocal()
            # Check connection pool parity baseline
            pool = db.bind.pool
            checked_out_before = pool.checkedout()
            
            # Check for pg_try_advisory_lock
            result = db.execute(text("SELECT pg_try_advisory_lock(113356)"))
            lock_acquired = result.scalar()
            
            if lock_acquired:
                logger.info("Acquired singleton advisory lock (113356). Running database prune...")
                # Run delete in transaction
                delete_res = db.execute(text(
                    "DELETE FROM pending_ingests WHERE expires_at < NOW() RETURNING validation_id"
                ))
                deleted_rows = delete_res.fetchall()
                deleted_count = len(deleted_rows)
                db.commit()
                
                logger.info(f"Successfully pruned {deleted_count} expired pending ingest rows.")
                
                if deleted_count > 0:
                    try:
                        TelemetryService.record_graph_pending_ingest_cleanup_rows(db, deleted_count)
                    except Exception as e:
                        logger.error(f"Failed to record cleanup rows telemetry: {e}")
            else:
                logger.info("Advisory lock (113356) denied. Cleanup worker iteration skipped.")
                
            # Reset backoff on success
            db_fail_delay = 5.0
            
        except (OperationalError, DBAPIError) as db_err:
            logger.error(f"Database connectivity issue encountered: {db_err}. Initiating backoff retry...")
            if db:
                db.close()
            
            # Execute backoff wait
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=db_fail_delay)
            except asyncio.TimeoutError:
                pass
            
            db_fail_delay = min(db_fail_delay * 2, 60.0)
            continue
            
        except Exception as e:
            logger.error(f"Unexpected error in cleanup cycle: {e}")
            
        finally:
            if db:
                if lock_acquired:
                    try:
                        # Release lock explicitly
                        db.execute(text("SELECT pg_advisory_unlock(113356)"))
                        db.commit()
                        logger.info("Advisory lock (113356) released.")
                    except Exception as unlock_err:
                        logger.error(f"Failed to release advisory lock: {unlock_err}")
                db.close()
            
            # Connection Pool Parity check
            if pool:
                checked_out_after = pool.checkedout()
                if checked_out_before != checked_out_after:
                    logger.error(
                        f"CONNECTION LEAK DETECTED! Sessions checked out before: {checked_out_before}, "
                        f"after: {checked_out_after}."
                    )
                    
        # Sleep for 5 minutes (300 seconds), interruptible by stop_event
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=300.0)
        except asyncio.TimeoutError:
            pass
            
    logger.info("Pending Ingest Cleanup Worker background loop stopped gracefully.")
