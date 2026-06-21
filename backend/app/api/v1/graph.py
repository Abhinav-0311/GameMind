from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
from app.database import get_db
from app.services.graph_traversal import graph_traversal_service
from app.dependencies import get_game_project_id

router = APIRouter(prefix="/graph", tags=["graph"])

@router.get("/subgraph")
def get_subgraph(
    seeds: List[str] = Query(..., description="Seed entity slugs to start subgraph extraction from"),
    depth: int = Query(2, description="Traversal hop depth"),
    max_nodes: int = Query(100, description="Maximum number of unique nodes to return"),
    max_edges: int = Query(500, description="Maximum number of edges to return"),
    direction: str = Query("both", description="Adjacent relationship direction: 'both', 'in', or 'out'"),
    as_of: Optional[str] = Query(None, description="ISO timestamp for historical traversal"),
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id)
):
    """
    Retrieve a subgraph neighborhood surrounding the specified seeds.
    Enforces safety limits and supports time-shifting.
    """
    # Parse as_of timestamp if provided
    parsed_as_of = None
    if as_of:
        try:
            parsed_as_of = datetime.fromisoformat(as_of)
        except ValueError:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={
                    "detail": {
                        "error": "Traversal validation failed",
                        "message": "Invalid ISO format for 'as_of' timestamp"
                    }
                }
            )

    # Validate safety limits and return custom 422 JSON payload on failure
    if depth > 4:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": {
                    "error": "Traversal validation failed",
                    "message": "Requested traversal depth exceeds maximum allowed depth of 4"
                }
            }
        )

    if max_nodes > 100:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": {
                    "error": "Traversal validation failed",
                    "message": "Requested node limit exceeds maximum allowed of 100"
                }
            }
        )

    if max_edges > 500:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": {
                    "error": "Traversal validation failed",
                    "message": "Requested edge limit exceeds maximum allowed of 500"
                }
            }
        )

    # Normalize seeds (support comma-separated inputs)
    normalized_seeds = []
    for seed in seeds:
        if "," in seed:
            normalized_seeds.extend([s.strip() for s in seed.split(",") if s.strip()])
        else:
            if seed.strip():
                normalized_seeds.append(seed.strip())

    if not normalized_seeds:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": {
                    "error": "Traversal validation failed",
                    "message": "At least one valid seed slug must be provided"
                }
            }
        )

    try:
        subgraph = graph_traversal_service.get_subgraph(
            db=db,
            seeds=normalized_seeds,
            depth=depth,
            max_nodes=max_nodes,
            max_edges=max_edges,
            direction=direction,
            as_of=parsed_as_of,
            game_project_id=game_project_id
        )
        return subgraph
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(e)}
        )


@router.get("/traverse")
def traverse(
    source: str = Query(..., description="Source entity slug"),
    target: str = Query(..., description="Target entity slug"),
    depth: int = Query(4, description="Maximum traversal depth"),
    max_paths: int = Query(25, description="Maximum path results"),
    algorithm: str = Query("bfs", description="Traversal algorithm: 'bfs' or 'dfs'"),
    as_of: Optional[str] = Query(None, description="ISO timestamp for historical pathfinding"),
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id)
):
    """
    Find paths between source and target entities using BFS or DFS.
    Enforces depth limits and returns custom 422 errors.
    """
    parsed_as_of = None
    if as_of:
        try:
            parsed_as_of = datetime.fromisoformat(as_of)
        except ValueError:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={
                    "detail": {
                        "error": "Traversal validation failed",
                        "message": "Invalid ISO format for 'as_of' timestamp"
                    }
                }
            )

    if depth > 4:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": {
                    "error": "Traversal validation failed",
                    "message": "Requested traversal depth exceeds maximum allowed depth of 4"
                }
            }
        )

    if max_paths > 25:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": {
                    "error": "Traversal validation failed",
                    "message": "Requested path limit exceeds maximum allowed of 25"
                }
            }
        )

    if algorithm.lower() not in ["bfs", "dfs"]:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": {
                    "error": "Traversal validation failed",
                    "message": "Algorithm must be either 'bfs' or 'dfs'"
                }
            }
        )

    try:
        path_results = graph_traversal_service.traverse(
            db=db,
            source=source,
            target=target,
            depth=depth,
            max_paths=max_paths,
            algorithm=algorithm,
            as_of=parsed_as_of,
            game_project_id=game_project_id
        )
        return path_results
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(e)}
        )


@router.get("/analytics")
def get_graph_analytics(
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id)
):
    """Retrieve topological metrics of the active graph state."""
    import time
    from app.services.graph_analytics import graph_analytics_service
    from app.services.telemetry import telemetry_service

    start_time = time.time()
    try:
        metrics = graph_analytics_service.get_topological_metrics(db, game_project_id=game_project_id)
        duration = time.time() - start_time
        telemetry_service.record_metric("graph_analytics_duration_seconds", duration)
        return metrics
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(e)}
        )

