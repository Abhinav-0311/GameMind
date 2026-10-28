"""Verify final content without changing artifacts or invoking a provider."""
import argparse
import copy
import hashlib
import json
import sys
from uuid import UUID

from app.design_agent.grounding import memory_is_unspecified


DEFER_WARNING = "Runtime integration explicitly deferred. Approved design only; no runtime release or materialization."


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def _paths(left, right, path=""):
    if _hash(left) == _hash(right):
        return []
    if isinstance(left, dict) and isinstance(right, dict):
        paths = []
        for key in sorted(left.keys() | right.keys()):
            child = path + "/" + key.replace("~", "~0").replace("/", "~1")
            paths.extend([child] if key not in left or key not in right else _paths(left[key], right[key], child))
        return paths
    if isinstance(left, list) and isinstance(right, list):
        paths = []
        for index in range(max(len(left), len(right))):
            child = path + "/" + str(index)
            paths.extend([child] if index >= len(left) or index >= len(right)
                         else _paths(left[index], right[index], child))
        return paths
    return [path]


def verify_final_integrity(reviewed, final, frozen_settings):
    """Compare exact JSON against independently re-derived, addition-only metadata."""
    if not all(isinstance(value, dict) for value in (reviewed, final, frozen_settings)):
        raise ValueError("Reviewed content, final content and frozen settings must be JSON objects.")
    expected = copy.deepcopy(reviewed)
    additions = []
    memory = expected.get("npc_memory_design", {})
    if memory_is_unspecified(reviewed, frozen_settings) and "memory_unspecified" not in memory:
        memory["memory_unspecified"] = True
        additions.append({"path": "/npc_memory_design/memory_unspecified", "value": True})
    if frozen_settings.get("defer_runtime") is True:
        runtime = expected["unity_runtime_preview"]
        if "runtime_deferred" not in runtime:
            runtime["runtime_deferred"] = True
            additions.append({"path": "/unity_runtime_preview/runtime_deferred", "value": True})
        warnings = runtime["warnings"]
        if DEFER_WARNING not in warnings:
            additions.append({"path": f"/unity_runtime_preview/warnings/{len(warnings)}", "value": DEFER_WARNING})
            warnings.append(DEFER_WARNING)
    reviewed_hash, final_hash = _hash(reviewed), _hash(final)
    exact = reviewed_hash == final_hash
    offending = [] if exact else _paths(expected, final)
    return {
        "reviewed_sha256": reviewed_hash, "final_sha256": final_hash,
        "differing_paths": _paths(reviewed, final), "permitted_additions": additions,
        "offending_paths": offending,
        "verdict": "EXACT" if exact else "MISMATCH" if offending else "EQUAL_EXCEPT_DOCUMENTED_METADATA",
    }


def read_run(run_id, database_url=None):
    """Read an approval-linked pair in one consistent PostgreSQL READ ONLY snapshot."""
    from sqlalchemy import create_engine, text

    if database_url is None:
        from app.config import settings
        database_url = settings.DATABASE_URL
    engine = create_engine(database_url, isolation_level="REPEATABLE READ")
    try:
        with engine.connect() as connection, connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            parameters = {"run_id": str(run_id)}
            run = connection.execute(text(
                "SELECT game_project_id, status, model_config FROM design_agent_runs WHERE id = :run_id"
            ), parameters).mappings().one_or_none()
            if run is None or run["status"] != "completed":
                raise ValueError("The selected run must exist and be completed.")
            parameters["project"] = run["game_project_id"]
            final = connection.execute(text(
                "SELECT content, immutable FROM design_agent_artifacts "
                "WHERE run_id = :run_id AND game_project_id = :project AND artifact_type = 'final'"
            ), parameters).mappings().one_or_none()
            reviewed = connection.execute(text(
                "SELECT artifact.content FROM design_agent_artifacts AS artifact "
                "JOIN design_agent_review_events AS review ON review.artifact_id = artifact.id "
                "AND review.run_id = artifact.run_id AND review.game_project_id = artifact.game_project_id "
                "WHERE artifact.run_id = :run_id AND artifact.game_project_id = :project "
                "AND artifact.artifact_type != 'final' AND review.decision = 'approve'"
            ), parameters).mappings().one_or_none()
            if final is None or final["immutable"] is not True or reviewed is None:
                raise ValueError("An immutable final and its recorded approved draft are required.")
            return reviewed["content"], final["content"], run["model_config"] or {}
    finally:
        engine.dispose()


def main(argv=None):
    from sqlalchemy.exc import SQLAlchemyError

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id", type=UUID)
    parser.add_argument("--database-url", help="Defaults to configured DATABASE_URL; never printed.")
    args = parser.parse_args(argv)
    try:
        report = verify_final_integrity(*read_run(args.run_id, args.database_url))
    except (ValueError, SQLAlchemyError) as error:
        print(f"Integrity verification failed ({type(error).__name__}); check run state and read-only database access.", file=sys.stderr)
        return 2
    print(json.dumps({"run_id": str(args.run_id), **report}, indent=2, ensure_ascii=False))
    return 1 if report["verdict"] == "MISMATCH" else 0


if __name__ == "__main__":
    raise SystemExit(main())
