import logging
from typing import Dict, Any, List

logger = logging.getLogger("gamemind.dialogue_style_engine")

class DialogueStyleEngine:
    @staticmethod
    def get_directives(personality: Dict[str, Any], emotions: Dict[str, int]) -> List[str]:
        """
        Formulates a list of tone directives (max 8) based on traits and active emotional states.
        """
        directives = []

        traits = personality.get("traits", {})
        
        # 1. Trait-driven directives
        courage = traits.get("courage", 50)
        sociability = traits.get("sociability", 50)
        intelligence = traits.get("intelligence", 50)
        temperament = traits.get("temperament", 50)

        # Sociability
        if sociability > 70:
            directives.append("Speak warmly, be expressive, and use friendly greetings.")
        elif sociability < 30:
            directives.append("Keep responses brief, cold, and concise.")

        # Temperament
        if temperament > 70:
            directives.append("Be impatient, dramatic, or easily excited.")
        elif temperament < 30:
            directives.append("Maintain a calm, measured, and stoic composure.")

        # Intelligence
        if intelligence > 70:
            directives.append("Use sophisticated vocabulary and analytical phrasing.")
        elif intelligence < 30:
            directives.append("Use simple, direct language and avoid complex terms.")

        # Courage
        if courage > 70:
            directives.append("Speak boldly, showing confidence and authority.")
        elif courage < 30:
            directives.append("Speak timidly, showing hesitation or self-doubt.")

        # 2. Emotion-driven directives (takes precedence)
        trust = emotions.get("trust", 50)
        fear = emotions.get("fear", 0)
        anger = emotions.get("anger", 0)
        curiosity = emotions.get("curiosity", 0)
        loyalty = emotions.get("loyalty", 0)

        if anger > 60:
            directives.append("Adopt a hostile, sharp, or accusatory tone.")
        if fear > 60:
            directives.append("Sound defensive, nervous, or submissive.")
        if trust > 70:
            directives.append("Speak with warmth, trust, and openness.")
        elif trust < 30:
            directives.append("Be suspicious, distant, and guarded.")
        if curiosity > 60:
            directives.append("Be inquisitive, asking probing questions.")
        if loyalty > 70:
            directives.append("Express steadfast commitment and support.")

        # Always deduplicate and enforce limit (max 8)
        unique_directives = []
        for d in directives:
            if d not in unique_directives:
                unique_directives.append(d)

        # If too empty, add a default directive
        if not unique_directives:
            unique_directives.append("Maintain a natural and realistic tone of voice.")

        return unique_directives[:8]
