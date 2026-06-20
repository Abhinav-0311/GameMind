import logging
import re
import uuid
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.session import Message
from app.services.telemetry_service import TelemetryService

logger = logging.getLogger("gamemind.conversation_continuity")

STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "else", "to", "of", "in", "on", "at", 
    "for", "with", "by", "about", "against", "between", "into", "through", "during", "before", 
    "after", "above", "below", "from", "up", "down", "out", "over", "under", "again", "further", 
    "once", "here", "there", "when", "where", "why", "how", "all", "any", "both", "each", "few", 
    "more", "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so", 
    "than", "too", "very", "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", 
    "your", "yours", "yourself", "yourselves", "he", "him", "his", "himself", "she", "her", "hers", 
    "herself", "it", "its", "itself", "they", "them", "their", "theirs", "themselves", "what", 
    "which", "who", "whom", "this", "that", "these", "those", "am", "is", "are", "was", "were", 
    "be", "been", "being", "have", "has", "had", "having", "do", "does", "did", "doing", "would", 
    "should", "could", "ought", "i'm", "you're", "he's", "she's", "it's", "we're", "they're", 
    "i've", "you've", "we've", "they've", "i'd", "you'd", "he'd", "she'd", "we'd", "they'd", 
    "i'll", "you'll", "he'll", "she'll", "we'll", "they'll", "isn't", "aren't", "wasn't", "weren't", 
    "hasn't", "haven't", "hadn't", "doesn't", "don't", "didn't", "won't", "wouldn't", "shan't", 
    "shouldn't", "can't", "cannot", "couldn't", "mustn't", "let's", "that's", "who's", "what's", 
    "here's", "there's", "when's", "where's", "why's", "how's", "hello", "hi", "hey", "please", "thanks"
}

class ConversationContinuity:
    @staticmethod
    def analyze_continuity(
        db: Session,
        conversation_id: Optional[uuid.UUID],
        player_message: str
    ) -> Dict[str, Any]:
        """
        Inspects up to 50 messages of conversation history to detect continuity keywords (max 20).
        """
        # Telemetry updates
        TelemetryService.record_narrative_metric(
            db,
            action_type="conversation_continuity_evaluations_total",
            npc_slug="system",
            model_used="conversation_continuity"
        )

        if not conversation_id:
            return {
                "keywords": [],
                "hits": [],
                "misses": [],
                "continuity_score": 0.0
            }

        # 1. Extract up to 20 unique keywords from player_message
        # We clean punctuation and extract capitalized/proper nouns or significant words
        words = re.findall(r"\b[a-zA-Z']+\b", player_message)
        
        candidates = []
        for idx, word in enumerate(words):
            cleaned = word.strip("'")
            if not cleaned:
                continue
            cleaned_lower = cleaned.lower()
            if cleaned_lower in STOP_WORDS:
                continue
            
            # Prioritize capitalized words (proper nouns/entities)
            is_proper = cleaned[0].isupper() and idx > 0
            candidates.append((cleaned, is_proper))

        # Sort: proper nouns first
        candidates.sort(key=lambda x: not x[1])

        # Select unique keywords up to 20
        unique_keywords = []
        for kw, _ in candidates:
            kw_lower = kw.lower()
            if kw_lower not in [k.lower() for k in unique_keywords]:
                unique_keywords.append(kw)
                if len(unique_keywords) >= 20:
                    break

        # 2. Fetch last 50 messages of history
        history_msgs = db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at.desc()).limit(50).all()

        if not history_msgs or not unique_keywords:
            return {
                "keywords": unique_keywords,
                "hits": [],
                "misses": unique_keywords.copy(),
                "continuity_score": 0.0
            }

        # Combine all history texts into a single search string
        history_text = " ".join([m.content for m in history_msgs]).lower()

        hits = []
        misses = []

        for kw in unique_keywords:
            # Look for word boundaries to avoid partial matches
            pattern = rf"\b{re.escape(kw.lower())}\b"
            if re.search(pattern, history_text):
                hits.append(kw)
            else:
                misses.append(kw)

        continuity_score = len(hits) / len(unique_keywords) if unique_keywords else 0.0

        return {
            "keywords": unique_keywords,
            "hits": hits,
            "misses": misses,
            "continuity_score": continuity_score
        }
