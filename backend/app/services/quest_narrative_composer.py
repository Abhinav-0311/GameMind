import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.npc import NPCProfile
from app.services.emotion_engine import EmotionEngine

logger = logging.getLogger("gamemind.quest_narrative_composer")

class QuestNarrativeComposer:
    @staticmethod
    def compose_narrative(
        db: Session,
        npc_profile: NPCProfile,
        template: Dict[str, Any],
        player_id: str,
        target_name: str,
        location: str,
        quantity: int = 1
    ) -> Dict[str, Any]:
        """
        Generates quest title, description, dialogue hooks, branches, and consequences,
        tailoring the tone to the NPC's emotional state.
        """
        # Fetch emotions to adjust tone
        emotions = EmotionEngine.get_emotional_state(db, npc_profile.slug, player_id)
        trust = emotions.get("trust", 50)
        fear = emotions.get("fear", 0)
        anger = emotions.get("anger", 0)
        loyalty = emotions.get("loyalty", 0)

        # Basic text substitution
        npc_name = npc_profile.name
        title_temp = template.get("title_template", "Quest for {npc_name}")
        desc_temp = template.get("description_template", "Help {npc_name} with their task.")

        title = title_temp.format(target_name=target_name, location=location, npc_name=npc_name)
        description = desc_temp.format(target_name=target_name, location=location, npc_name=npc_name, quantity=quantity)

        # Tone-tailored dialogue hook
        if anger > 50:
            dialogue_hook = f"I've had enough of this! Go deal with the {target_name} at {location} immediately. Don't make me ask twice."
            animation = "angry"
        elif fear > 50:
            dialogue_hook = f"Please... I'm terrified of what {target_name} might do. Could you go to {location} and handle this?"
            animation = "fearful"
        elif trust > 70:
            dialogue_hook = f"Ah, it's good to see you, my friend. I have a critical task involving {target_name} at {location}. I know I can count on you."
            animation = "friendly"
        elif loyalty > 50:
            dialogue_hook = f"For the honor of our faction! We must secure {location} by dealing with {target_name}. Are you ready to serve?"
            animation = "determined"
        else:
            dialogue_hook = f"I have a task for you. We need to look into {target_name} at {location}. Let me know if you can assist."
            animation = "neutral"

        # Construct resolution branches (at most 5)
        branches = [
            {
                "branch_index": 0,
                "name": "Direct Confrontation",
                "description": f"Confront the {target_name} directly with force.",
                "choice_prompt": "I will face them head-on."
            },
            {
                "branch_index": 1,
                "name": "Subtle Negotiation",
                "description": f"Attempt to bribe or negotiate with the {target_name}.",
                "choice_prompt": "Is there a peaceful way to resolve this?"
            }
        ]

        # Construct consequences (at most 10)
        npc_faction = npc_profile.faction_alignment or "neutral_faction"
        consequences = [
            {
                "source": npc_profile.slug,
                "target": "player",
                "type": "trust",
                "value": "increase"
            },
            {
                "source": npc_faction,
                "target": "player",
                "type": "standing",
                "value": "increase"
            }
        ]

        return {
            "title": title,
            "description": description,
            "dialogue_hook": dialogue_hook,
            "animation_hint": animation,
            "branches": branches,
            "consequences": consequences
        }
