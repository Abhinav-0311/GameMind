using System;
using System.Collections.Generic;

namespace GameMind.Contracts
{
    [Serializable]
    public class DialogueCitation
    {
        public string document_id;
        public string chunk_id;
        public string title;
        public float similarity;
    }

    [Serializable]
    public class NPCEmotions
    {
        public float trust;
        public float fear;
        public float anger;
        public float curiosity;
        public float loyalty;
    }

    [Serializable]
    public class DialogueChatResponse
    {
        public string api_version;
        public string npc_slug;
        public string response_text;
        public string suggested_animation;
        public NPCEmotions npc_emotions;
        public List<DialogueCitation> citations;
        public string conversation_id;
    }

    [Serializable]
    public class QuestReward
    {
        public int gold;
        public int xp;
        public List<string> items;
    }

    [Serializable]
    public class QuestGeneratedResponse
    {
        public string api_version;
        public string npc_slug;
        public string title;
        public string description;
        public string difficulty;
        public QuestReward rewards;
        public List<QuestObjectiveDto> objectives;
    }

    [Serializable]
    public class QuestObjectiveDto
    {
        public string id;
        public int objective_index;
        public string description;
        public string target_type;
        public string target_id;
        public int quantity_required;
    }

    [Serializable]
    public class ErrorDetail
    {
        public string code;
        public string message;
        public int? retry_after_seconds;
    }

    [Serializable]
    public class ErrorEnvelope
    {
        public string api_version;
        public ErrorDetail error;
    }

    [Serializable]
    public class NpcProfileDto
    {
        public string id;
        public string slug;
        public string name;
        public string title;
        public string personality_summary;
        public string dialogue_style;
    }

    [Serializable]
    public class QuestDto
    {
        public string id;
        public string npc_slug;
        public string title;
        public string description;
        public string difficulty;
        public int gold_reward;
        public int xp_reward;
        public List<string> item_rewards;
        public List<QuestObjectiveDto> objectives;
    }

    [Serializable]
    public class MemoryDto
    {
        public string id;
        public string npc_id;
        public string memory_text;
        public string memory_type;
        public float importance_score;
    }

    [Serializable]
    public class WorldFlagDto
    {
        public string game_project_id;
        public string flag_key;
        public string flag_value;
        public bool is_active;
        public int priority;
    }

    [Serializable]
    public class BlueprintRuntimeBundleResponse
    {
        public string api_version;
        public string blueprint_id;
        public string game_project_id;
        public List<NpcProfileDto> npcs;
        public List<QuestDto> quests;
        public List<MemoryDto> memories;
        public List<WorldFlagDto> world_flags;
    }

    [Serializable]
    public class QuestProgressResponse
    {
        public string id;
        public string player_id;
        public string quest_id;
        public string quest_giver_slug;
        public string status;
        public string started_at;
    }

    [Serializable]
    public class HintResponse
    {
        public int hint_level;
        public string hint;
        public string spoiler_level;
    }

    [Serializable]
    public class HintStatusResponse
    {
        public string quest_id;
        public string player_id;
        public int current_level;
        public int cooldown_remaining_seconds;
    }
}
