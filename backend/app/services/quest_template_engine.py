import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from app.services.graph_cache import graph_cache

logger = logging.getLogger("gamemind.quest_template_engine")

QUEST_TEMPLATES = [
    {
        "template_slug": "eliminate_threat",
        "title_template": "Eliminate the {target_name}",
        "description_template": "A threat has emerged in the area. Travel to {location} and defeat the {target_name} to restore order.",
        "difficulty": "Hard",
        "target_type": "kill",
        "objectives": [
            {
                "objective_index": 0,
                "description": "Defeat {quantity} {target_name} at {location}",
                "target_type": "kill",
                "target_id": "{target_id}",
                "quantity_required": "{quantity}"
            }
        ],
        "reward_scaling": {
            "gold_multiplier": 15,
            "xp_multiplier": 50,
            "base_items": ["health_potion", "steel_sword"]
        },
        "faction_modifier": 10.0
    },
    {
        "template_slug": "fetch_supplies",
        "title_template": "Acquire {target_name}",
        "description_template": "We are running low on supplies. Go gather {quantity} {target_name} and bring them to {npc_name}.",
        "difficulty": "Medium",
        "target_type": "retrieve",
        "objectives": [
            {
                "objective_index": 0,
                "description": "Collect {quantity} {target_name}",
                "target_type": "retrieve",
                "target_id": "{target_id}",
                "quantity_required": "{quantity}"
            }
        ],
        "reward_scaling": {
            "gold_multiplier": 10,
            "xp_multiplier": 35,
            "base_items": ["mana_potion", "leather_boots"]
        },
        "faction_modifier": 5.0
    },
    {
        "template_slug": "diplomatic_delivery",
        "title_template": "Message to {target_name}",
        "description_template": "Deliver an important message to {target_name} at {location} regarding the recent world developments.",
        "difficulty": "Easy",
        "target_type": "speak",
        "objectives": [
            {
                "objective_index": 0,
                "description": "Speak with {target_name} at {location}",
                "target_type": "speak",
                "target_id": "{target_id}",
                "quantity_required": 1
            }
        ],
        "reward_scaling": {
            "gold_multiplier": 5,
            "xp_multiplier": 25,
            "base_items": ["scroll_of_teleportation"]
        },
        "faction_modifier": 8.0
    }
]

class QuestTemplateEngine:
    @staticmethod
    def get_templates() -> List[Dict[str, Any]]:
        """Return all available templates."""
        return QUEST_TEMPLATES

    @staticmethod
    def select_template(target_type: Optional[str] = None) -> Dict[str, Any]:
        """Select a template by target_type, falling back to a default one."""
        for template in QUEST_TEMPLATES:
            if target_type and template["target_type"] == target_type:
                return template
        return QUEST_TEMPLATES[0]

    @staticmethod
    def scale_rewards(
        player_level: int,
        difficulty: str,
        reward_scaling: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Scales gold, xp and items rewards relative to player_level and difficulty.
        Enforces MAX_REWARDS_PER_QUEST limit of 5.
        Returns:
            rewards dict (gold, xp, items)
            is_adjusted (boolean indicating if clamping occurred)
        """
        diff = difficulty.lower()
        if diff == "easy":
            diff_mult = 0.8
        elif diff == "hard":
            diff_mult = 1.5
        else:
            diff_mult = 1.0

        gold = int(player_level * reward_scaling.get("gold_multiplier", 10) * diff_mult)
        xp = int(player_level * reward_scaling.get("xp_multiplier", 30) * diff_mult)
        items = list(reward_scaling.get("base_items", []))

        # Max rewards per quest constraint = 5.
        # Let's count rewards as: 1 (if gold > 0) + 1 (if xp > 0) + len(items).
        # If total exceeds 5, we clamp items list and record adjustment.
        total_non_items = 0
        if gold > 0:
            total_non_items += 1
        if xp > 0:
            total_non_items += 1

        max_items = 5 - total_non_items
        is_adjusted = False
        if len(items) > max_items:
            items = items[:max_items]
            is_adjusted = True

        return {
            "gold": gold,
            "xp": xp,
            "items": items
        }, is_adjusted

    @staticmethod
    def get_cached_template(template_slug: str) -> Tuple[Optional[Dict[str, Any]], bool]:
        """
        Check template cache using version-stamp key logic.
        Quest Template Cache key format: graph:cache:quest_templates:<template_slug>
        """
        try:
            redis_client = graph_cache.redis
            cache_key = f"graph:cache:quest_templates:{template_slug}"
            data = redis_client.get(cache_key)
            if data:
                return json.loads(data.decode("utf-8")), True
        except Exception as e:
            logger.error(f"Error reading cached template: {e}")
        return None, False

    @staticmethod
    def set_cached_template(template_slug: str, template_data: Dict[str, Any], ttl: int = 3600) -> None:
        """Cache template data."""
        try:
            redis_client = graph_cache.redis
            cache_key = f"graph:cache:quest_templates:{template_slug}"
            redis_client.set(cache_key, json.dumps(template_data).encode("utf-8"), ex=ttl)
        except Exception as e:
            logger.error(f"Error caching template: {e}")
