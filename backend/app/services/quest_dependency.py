import logging
from typing import Dict, List, Tuple, Optional, Set, Any
from sqlalchemy.orm import Session
from app.models.quest import Quest, QuestProgress
from app.models.graph import WorldEntity, WorldRelationship
from app.services.telemetry_service import TelemetryService

logger = logging.getLogger("gamemind.quest_dependency")

class QuestDependencyAnalyzer:
    @classmethod
    def _build_quest_adjacency(cls, db: Session) -> Tuple[Dict[str, List[str]], Set[str]]:
        """
        Builds the quest dependency adjacency list.
        Returns:
            adjacency_list: Dict[quest_slug, List[dependency_quest_slugs]]
            nodes: Set[quest_slugs]
        """
        # Fetch all active prerequisite relationships in the graph
        prereqs = db.query(WorldRelationship).filter(
            WorldRelationship.rel_type == "prerequisite",
            WorldRelationship.valid_to.is_(None)
        ).all()

        adj: Dict[str, List[str]] = {}
        nodes: Set[str] = set()

        for rel in prereqs:
            # Source is parent (prerequisite), Target is child (dependent quest)
            src_ent = db.query(WorldEntity).filter(WorldEntity.id == rel.source_id).first()
            tgt_ent = db.query(WorldEntity).filter(WorldEntity.id == rel.target_id).first()
            if not src_ent or not tgt_ent:
                continue

            src_slug = src_ent.slug
            tgt_slug = tgt_ent.slug

            nodes.add(src_slug)
            nodes.add(tgt_slug)

            if src_slug not in adj:
                adj[src_slug] = []
            adj[src_slug].append(tgt_slug)

        # Ensure all nodes exist in adjacency dictionary
        for node in nodes:
            if node not in adj:
                adj[node] = []

        return adj, nodes

    @classmethod
    def detect_cycles(cls, db: Session) -> bool:
        """
        DFS coloring cycle detection:
        0 (White) = Unvisited
        1 (Gray) = Visiting/Active in recursion
        2 (Black) = Visited
        """
        adj, nodes = cls._build_quest_adjacency(db)
        state: Dict[str, int] = {node: 0 for node in nodes}

        def dfs(u: str) -> bool:
            state[u] = 1 # Gray
            for v in adj.get(u, []):
                if state[v] == 1: # Encountered Gray node -> cycle detected
                    return True
                elif state[v] == 0:
                    if dfs(v):
                        return True
            state[u] = 2 # Black
            return False

        has_cycle = False
        for node in nodes:
            if state[node] == 0:
                if dfs(node):
                    has_cycle = True
                    break

        if has_cycle:
            # Log cycle detected telemetry
            TelemetryService.record_narrative_metric(
                db,
                action_type="quest_dependency_cycles_detected_total",
                npc_slug="system",
                model_used="quest_dependency",
                error_str="Cycle detected in quest dependency graph"
            )

        return has_cycle

    @classmethod
    def topological_sort(cls, db: Session) -> List[str]:
        """
        DFS-based topological sort. Returns quest slugs in dependency resolution order.
        Raises ValueError if cycle is detected.
        """
        adj, nodes = cls._build_quest_adjacency(db)
        state: Dict[str, int] = {node: 0 for node in nodes}
        stack: List[str] = []

        def dfs(u: str):
            state[u] = 1 # Gray
            for v in adj.get(u, []):
                if state[v] == 1:
                    raise ValueError("Quest dependency graph contains a cycle; cannot perform topological sort.")
                elif state[v] == 0:
                    dfs(v)
            state[u] = 2 # Black
            stack.append(u)

        for node in nodes:
            if state[node] == 0:
                try:
                    dfs(node)
                except ValueError as e:
                    # Log cycle detected telemetry
                    TelemetryService.record_narrative_metric(
                        db,
                        action_type="quest_dependency_cycles_detected_total",
                        npc_slug="system",
                        model_used="quest_dependency",
                        error_str=str(e)
                    )
                    raise e

        # Topological order is reversed stack
        return stack[::-1]

    @classmethod
    def analyze_quest_dependencies(cls, db: Session) -> Dict[str, Any]:
        """Runs diagnostics on the quest dependency graph."""
        has_cycles = cls.detect_cycles(db)
        top_order = None
        if not has_cycles:
            top_order = cls.topological_sort(db)
        return {
            "has_cycles": has_cycles,
            "topological_order": top_order
        }

    @classmethod
    def is_eligible(cls, db: Session, player_id: str, quest_id: str) -> Tuple[bool, Optional[str]]:
        """
        Evaluates whether a player has completed all prerequisite quests.
        A quest is completed if player has QuestProgress(status="completed") for it.
        """
        quest = db.query(Quest).filter(Quest.id == quest_id).first()
        if not quest:
            return False, "Quest not found."

        # Verify eligibility check telemetry
        TelemetryService.record_narrative_metric(
            db,
            action_type="narrative_consistency_checks_total",
            npc_slug="system",
            model_used="quest_eligibility",
            error_str=None
        )

        # Quests can be referenced in the graph by their title slug or string ID
        quest_slugs = [str(quest.id), quest.title.lower().replace(" ", "_")]

        # Query all active prerequisite relationships pointing to this quest slug
        prereqs = db.query(WorldRelationship).filter(
            WorldRelationship.rel_type == "prerequisite",
            WorldRelationship.valid_to.is_(None)
        ).all()

        for rel in prereqs:
            # Source is parent (prerequisite), Target is child (this quest)
            src_ent = db.query(WorldEntity).filter(WorldEntity.id == rel.source_id).first()
            tgt_ent = db.query(WorldEntity).filter(WorldEntity.id == rel.target_id).first()
            if not src_ent or not tgt_ent:
                continue

            # Check if this relationship actually targets this quest
            if tgt_ent.slug in quest_slugs:
                # Source must be completed by the player
                parent_slug = src_ent.slug
                
                # Check QuestProgress for parent quest
                # The parent might be referenced by its ID or title
                parent_quest = db.query(Quest).filter(
                    (Quest.id == parent_slug) | 
                    (Quest.title.ilike(parent_slug.replace("_", " ")))
                ).first()

                if not parent_quest:
                    # If not found directly in quests table, check if parent_slug is a UUID
                    try:
                        import uuid
                        parent_uuid = uuid.UUID(parent_slug)
                        parent_quest = db.query(Quest).filter(Quest.id == parent_uuid).first()
                    except ValueError:
                        pass

                if not parent_quest:
                    # Prerequisite exists in graph but quest metadata is missing
                    return False, f"Prerequisite quest metadata '{parent_slug}' not found."

                # Verify parent quest progress
                progress = db.query(QuestProgress).filter(
                    QuestProgress.player_id == player_id,
                    QuestProgress.quest_id == parent_quest.id
                ).first()

                if not progress or progress.status != "completed":
                    return False, f"Prerequisite quest '{parent_quest.title}' is not completed."

        return True, None
