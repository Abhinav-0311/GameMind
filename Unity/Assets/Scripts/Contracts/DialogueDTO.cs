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
}
