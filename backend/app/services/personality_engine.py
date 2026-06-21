from typing import Dict, Any
from sqlalchemy.orm import Session
from app.models.npc import NPCProfile
from app.services.telemetry_service import TelemetryService

class PersonalityEngine:
    @staticmethod
    def evaluate_personality(db: Session, npc_slug: str, game_project_id: str = "default_project") -> Dict[str, Any]:
        """
        Loads the NPC Profile's personality traits, behavioral tendencies,
        and conversation preferences.
        """
        # Telemetry updates
        TelemetryService.record_narrative_metric(
            db,
            action_type="personality_profile_evaluations_total",
            npc_slug=npc_slug,
            model_used="personality_engine"
        )
        
        npc = db.query(NPCProfile).filter(
            NPCProfile.slug == npc_slug,
            NPCProfile.game_project_id == game_project_id,
            NPCProfile.deleted_at.is_(None)
        ).first()
        
        if not npc:
            return PersonalityEngine.get_defaults()
            
        metadata = npc.metadata_json or {}
        personality = metadata.get("personality", {})
        
        traits = personality.get("traits", {})
        tendencies = personality.get("behavioral_tendencies", {})
        preferences = personality.get("conversation_preferences", {})
        modifiers = personality.get("relationship_modifiers", {})
        
        # Merge with defaults
        defaults = PersonalityEngine.get_defaults()
        
        merged_traits = {**defaults["traits"], **traits}
        merged_tendencies = {**defaults["behavioral_tendencies"], **tendencies}
        merged_preferences = {**defaults["conversation_preferences"], **preferences}
        merged_modifiers = {**defaults["relationship_modifiers"], **modifiers}
        
        return {
            "traits": merged_traits,
            "behavioral_tendencies": merged_tendencies,
            "conversation_preferences": merged_preferences,
            "relationship_modifiers": merged_modifiers
        }
        
    @staticmethod
    def get_defaults() -> Dict[str, Any]:
        return {
            "traits": {
                "courage": 50,
                "sociability": 50,
                "intelligence": 50,
                "temperament": 50,
                "loyalty": 50
            },
            "behavioral_tendencies": {
                "prefers_diplomacy": True
            },
            "conversation_preferences": {
                "friendly_greeting": True
            },
            "relationship_modifiers": {
                "trust_gain_multiplier": 1.0,
                "anger_loss_multiplier": 1.0
            }
        }
