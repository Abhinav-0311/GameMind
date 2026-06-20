import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.repositories.graph_repository import graph_repo
from app.models.graph import WorldEntity, WorldRelationship
from app.models.quest import Quest, QuestProgress
from app.services.emotion_engine import EmotionEngine
from app.services.telemetry_service import TelemetryService

logger = logging.getLogger("gamemind.conversation_planner")

class ConversationPlanner:
    @staticmethod
    def generate_plan(
        db: Session,
        npc_slug: str,
        player_id: str,
        player_message: str,
        history: Optional[List] = None
    ) -> Dict[str, Any]:
        """
        Generates a conversation plan including topic priorities and up to 5 goals.
        """
        # Telemetry updates
        TelemetryService.record_narrative_metric(
            db,
            action_type="conversation_plans_generated_total",
            npc_slug=npc_slug,
            model_used="conversation_planner"
        )

        # 1. Fetch adjacent graph nodes
        npc_entity = graph_repo.get_entity_by_slug(db, npc_slug)
        adjacent_nodes = []
        if npc_entity:
            rels = graph_repo.get_adjacent_relationships(db, npc_entity.id)
            for rel in rels:
                other_id = rel.target_id if rel.source_id == npc_entity.id else rel.source_id
                other_ent = db.query(WorldEntity).filter(WorldEntity.id == other_id).first()
                if other_ent:
                    # Get name from active version if possible
                    ver = graph_repo.get_active_entity_version(db, other_ent.id)
                    name = ver.name if ver else other_ent.slug
                    adjacent_nodes.append({
                        "slug": other_ent.slug,
                        "name": name,
                        "rel_type": rel.rel_type
                    })

        # 2. Match inputs to determine topic priorities
        topic_priorities = []
        msg_lower = player_message.lower()
        for node in adjacent_nodes:
            slug_match = node["slug"].lower() in msg_lower
            name_match = node["name"].lower() in msg_lower
            
            # Simple keyword matching
            priority = 10 if (slug_match or name_match) else 1
            topic_priorities.append({
                "topic": node["name"],
                "slug": node["slug"],
                "priority": priority
            })

        # Sort topics: highest priority first, then alphabetically
        topic_priorities.sort(key=lambda x: (-x["priority"], x["topic"]))

        # 3. Formulate conversation goals (max 5)
        goals = []

        # Get NPC emotions
        emotions = EmotionEngine.get_emotional_state(db, npc_slug, player_id)
        
        # Check active quests
        active_quests = db.query(QuestProgress, Quest).join(Quest, Quest.id == QuestProgress.quest_id).filter(
            QuestProgress.player_id == player_id,
            QuestProgress.quest_giver_slug == npc_slug,
            QuestProgress.status == "active"
        ).all()

        # Build dynamic goals
        if active_quests:
            for progress, quest in active_quests[:2]:
                goals.append(f"Guide player towards completing the quest: '{quest.title}'")

        # Emotion-driven goals
        if emotions.get("trust", 50) < 40:
            goals.append("Remain cautious and verify player's intentions due to low trust")
        elif emotions.get("trust", 50) > 75:
            goals.append("Share information transparently as a trusted ally")

        if emotions.get("fear", 0) > 60:
            goals.append("Keep interactions formal and cautious out of fear")

        if emotions.get("anger", 0) > 50:
            goals.append("Express displeasure or skepticism in dialogue")

        if emotions.get("curiosity", 0) > 60:
            goals.append("Inquire more about the player's background and recent actions")

        # Top matched topics goals
        matched_topics = [t for t in topic_priorities if t["priority"] > 1]
        for t in matched_topics[:2]:
            goals.append(f"Address the player's query regarding {t['topic']}")

        # Default fallback goal if we have room
        if not goals:
            goals.append("Respond to the player's message politely and remain in character")

        # Cap goals at 5
        goals = goals[:5]

        return {
            "topic_priorities": topic_priorities,
            "goals": goals
        }
