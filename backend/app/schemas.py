from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import List, Optional, Any, Dict
import re

# Chunk Schemas
class ChunkResponse(BaseModel):
    id: UUID
    chunk_index: int
    content: str
    metadata: Optional[Dict[str, Any]] = Field(default=None, alias="metadata")

    @model_validator(mode="before")
    @classmethod
    def resolve_sqlalchemy_metadata(cls, data: Any) -> Any:
        if data and not isinstance(data, dict):
            attribs = {}
            for field in cls.model_fields.keys():
                if field == "metadata":
                    attribs["metadata"] = getattr(data, "metadata_json", None)
                elif hasattr(data, field):
                    attribs[field] = getattr(data, field)
            return attribs
        return data

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )

# Document Schemas
class DocumentResponse(BaseModel):
    id: UUID
    title: str
    content_type: str
    created_at: datetime
    updated_at: datetime
    chunks_count: int

    model_config = ConfigDict(
        from_attributes=True
    )

class DocumentDetailResponse(DocumentResponse):
    chunks: List[ChunkResponse] = []

# Query Schemas
class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Lore search query text")
    limit: Optional[int] = Field(default=5, ge=1, le=20, description="Max number of items to retrieve")

class QueryResultResponse(BaseModel):
    chunk_id: str
    content: str
    document_id: Optional[str]
    title: Optional[str]
    chunk_index: Optional[int]
    similarity: float
    confidence: str

class QueryResponse(BaseModel):
    query: str
    results: List[QueryResultResponse]
    message: Optional[str] = None


# NPC Profile Schemas
class NPCProfileBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Display name of the NPC")
    title: Optional[str] = Field(default=None, max_length=100, description="Rank or title of the NPC")
    personality_summary: str = Field(..., min_length=1, description="Core background and personality details")
    dialogue_style: Optional[str] = Field(default=None, description="Instructions on speech patterns/style")
    voice_profile: Optional[str] = Field(default=None, max_length=100, description="TTS voice identifier")
    faction_alignment: Optional[str] = Field(default=None, max_length=100, description="Associated faction slug")
    animation_hints: Optional[Dict[str, Any]] = Field(default=None, description="Emotion to animation name mapping")
    memory_settings: Optional[Dict[str, Any]] = Field(default=None, description="Memory parameters")
    metadata: Optional[Dict[str, Any]] = Field(default=None, alias="metadata", description="Extra custom metadata")

    @model_validator(mode="before")
    @classmethod
    def resolve_sqlalchemy_metadata(cls, data: Any) -> Any:
        if data and not isinstance(data, dict):
            attribs = {}
            for field in cls.model_fields.keys():
                if field == "metadata":
                    attribs["metadata"] = getattr(data, "metadata_json", None)
                elif hasattr(data, field):
                    attribs[field] = getattr(data, field)
            for extra in ["id", "slug", "created_at", "updated_at"]:
                if hasattr(data, extra):
                    attribs[extra] = getattr(data, extra)
            return attribs
        return data

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )

class NPCProfileCreate(NPCProfileBase):
    slug: str = Field(..., min_length=3, max_length=100, description="Unique URL-safe string identifier")

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9_-]+$", v):
            raise ValueError("Slug must be lowercase and contain only alphanumeric characters, underscores, or hyphens.")
        return v

class NPCProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    title: Optional[str] = Field(default=None, max_length=100)
    personality_summary: Optional[str] = Field(default=None, min_length=1)
    dialogue_style: Optional[str] = Field(default=None)
    voice_profile: Optional[str] = Field(default=None, max_length=100)
    faction_alignment: Optional[str] = Field(default=None, max_length=100)
    animation_hints: Optional[Dict[str, Any]] = Field(default=None)
    memory_settings: Optional[Dict[str, Any]] = Field(default=None)
    metadata: Optional[Dict[str, Any]] = Field(default=None, alias="metadata")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )

class NPCProfileResponse(NPCProfileBase):
    id: UUID
    slug: str
    created_at: datetime
    updated_at: datetime


# Dialogue Assembly Schemas
class DialogueAssembleRequest(BaseModel):
    npc_slug: str = Field(..., min_length=1, description="Unique NPC slug identification")
    player_message: str = Field(..., min_length=1, description="Raw message input from player")
    selected_chunk_ids: Optional[List[UUID]] = Field(default=None, description="Database chunk identifiers to retrieve context from")
    player_id: Optional[str] = Field(default="default_player", description="Player identifier for relationship/quest tracking")
    conversation_id: Optional[UUID] = Field(default=None, description="Optional active conversation session identifier")

class EmotionUpdateRequest(BaseModel):
    npc_slug: str = Field(..., min_length=1, description="NPC slug identifier")
    player_id: Optional[str] = Field(default="default_player", description="Player identifier")
    updates: Dict[str, int] = Field(..., description="Dict of emotion updates, e.g. {'trust': 70, 'anger': 10}")
    reason: Optional[str] = Field(default=None, description="Optional explanation for the update")

    @field_validator("updates")
    @classmethod
    def validate_emotion_updates(cls, v: Dict[str, int]) -> Dict[str, int]:
        valid_emotions = {"trust", "fear", "anger", "curiosity", "loyalty"}
        for k, val in v.items():
            if k not in valid_emotions:
                raise ValueError(f"Invalid emotion key '{k}'. Must be one of {valid_emotions}")
            if not isinstance(val, int) or val < 0 or val > 100:
                raise ValueError(f"Value for '{k}' must be an integer between 0 and 100.")
        return v

class EmotionResponse(BaseModel):
    npc_slug: str
    player_id: str
    emotions: Dict[str, int]


class RetrievedChunkMetadata(BaseModel):
    id: UUID
    document_id: UUID
    chunk_index: int
    character_count: int

    model_config = ConfigDict(
        from_attributes=True
    )

class DialogueAssembleResponse(BaseModel):
    npc_slug: str
    player_message: str
    system_prompt: str
    npc_context: str
    retrieved_context: str
    assembled_prompt: str
    prompt_version: str
    character_count: int
    estimated_tokens: int
    retrieved_chunk_count: int
    retrieved_chunks: List[RetrievedChunkMetadata]
    warnings: List[str] = []


# Dialogue Chat Live Schemas
class DialogueChatRequest(DialogueAssembleRequest):
    prompt_version: Optional[str] = Field(default="v1", description="Prompt template version identifier")
    model_override: Optional[str] = Field(default=None, description="Optional override for the LLM model identifier")
    conversation_id: Optional[UUID] = Field(default=None, description="Optional active conversation session identifier")

class SafetyRatingSchema(BaseModel):
    category: str
    probability: str
    blocked: Optional[bool] = None

class ChatTelemetrySchema(BaseModel):
    latency_ms: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    safety_ratings: List[SafetyRatingSchema] = []
    safety_blocked: Optional[bool] = None
    error: Optional[str] = None

class DialogueCitation(BaseModel):
    document_id: UUID
    chunk_id: UUID
    title: str
    similarity: float

    model_config = ConfigDict(
        from_attributes=True
    )

class NPCEmotions(BaseModel):
    trust: float
    fear: float
    anger: float
    curiosity: float
    loyalty: float

    model_config = ConfigDict(
        from_attributes=True
    )

class DialogueChatResponse(BaseModel):
    api_version: str = "1.0"
    npc_slug: str
    response_text: str
    suggested_animation: Optional[str] = None
    npc_emotions: Optional[NPCEmotions] = None
    citations: List[DialogueCitation] = []
    conversation_id: Optional[UUID] = None
    # Keep old fields as optional to prevent breaking regression tests
    prompt_version: Optional[str] = None
    model_used: Optional[str] = None
    llm_provider: Optional[str] = None
    telemetry: Optional[ChatTelemetrySchema] = None
    warnings: Optional[List[str]] = []

    model_config = ConfigDict(
        from_attributes=True
    )

# Conversation Schemas
class ConversationCreate(BaseModel):
    npc_slug: str = Field(..., min_length=1, description="Target NPC slug identifier")

class MessageResponse(BaseModel):
    id: UUID
    sender: str
    content: str
    metadata: Optional[Dict[str, Any]] = Field(default=None, alias="metadata")
    created_at: datetime

    @model_validator(mode="before")
    @classmethod
    def resolve_sqlalchemy_metadata(cls, data: Any) -> Any:
        if data and not isinstance(data, dict):
            attribs = {}
            for field in cls.model_fields.keys():
                if field == "metadata":
                    attribs["metadata"] = getattr(data, "metadata_json", None)
                elif hasattr(data, field):
                    attribs[field] = getattr(data, field)
            return attribs
        return data

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )

class ConversationResponse(BaseModel):
    id: UUID
    npc_id: UUID
    npc_slug: str
    title: Optional[str] = None
    conversation_summary: Optional[str] = None
    summary_version: int = 0
    summary_updated_at: Optional[datetime] = None
    status: str = "active"
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )

class ConversationDetailResponse(ConversationResponse):
    messages: List[MessageResponse] = []

# Memory Schemas
class NPCMemoryCreate(BaseModel):
    npc_slug: str = Field(..., min_length=1, description="Target NPC slug identifier")
    conversation_id: Optional[UUID] = Field(default=None, description="Optional associated conversation UUID")
    memory_text: str = Field(..., min_length=1, description="Raw text of the memory")
    memory_type: str = Field(default="episodic", description="Type of the memory")
    importance_score: float = Field(default=1.0, ge=1.0, le=10.0, description="Importance score of the memory")

class NPCMemoryResponse(BaseModel):
    id: UUID
    npc_id: UUID
    conversation_id: Optional[UUID] = None
    memory_text: str
    memory_type: str
    importance_score: float
    chroma_indexed: bool
    archived: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )

class MemoryConsolidateRequest(BaseModel):
    npc_slug: str = Field(..., min_length=1, description="Target NPC slug identifier")

class MemoryConsolidateResponse(BaseModel):
    npc_slug: str
    clusters_processed: int
    archived_memories_count: int


# World State Schemas
class WorldStateFlagResponse(BaseModel):
    flag_key: str
    flag_value: str
    is_active: bool
    priority: int
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )

class WorldStateFlagToggle(BaseModel):
    flag_key: str = Field(..., min_length=1)
    flag_value: str = Field(..., min_length=1)
    is_active: bool
    priority: Optional[int] = 0

# NPC Relationship Schemas
class NPCRelationshipResponse(BaseModel):
    id: UUID
    player_id: str
    npc_slug: str
    trust: int
    respect: int
    friendship: int
    fear: int
    last_reason: Optional[str] = None
    updated_at: datetime
    standing: Optional[str] = None

    model_config = ConfigDict(
        from_attributes=True
    )

class NPCRelationshipUpdate(BaseModel):
    npc_slug: str = Field(..., min_length=1)
    player_id: Optional[str] = "default_player"
    trust: Optional[int] = Field(default=50, ge=0, le=100)
    respect: Optional[int] = Field(default=50, ge=0, le=100)
    friendship: Optional[int] = Field(default=50, ge=0, le=100)
    fear: Optional[int] = Field(default=0, ge=0, le=100)
    last_reason: Optional[str] = None

# Quest Objective Schemas
class QuestObjectiveCreate(BaseModel):
    objective_index: int = Field(..., ge=0)
    description: str = Field(..., min_length=1)
    target_type: str = Field(..., min_length=1)  # e.g., 'kill', 'retrieve', 'speak'
    target_id: str = Field(..., min_length=1)
    quantity_required: int = Field(default=1, ge=1)

class QuestObjectiveResponse(QuestObjectiveCreate):
    id: UUID

    model_config = ConfigDict(from_attributes=True)

# Quest Schemas
class QuestCreate(BaseModel):
    npc_slug: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    difficulty: Optional[str] = "Medium"
    gold_reward: Optional[int] = 0
    xp_reward: Optional[int] = 0
    item_rewards: Optional[List[str]] = None
    objectives: List[QuestObjectiveCreate]

class QuestResponse(BaseModel):
    id: UUID
    npc_slug: str
    title: str
    description: str
    difficulty: str
    gold_reward: int
    xp_reward: int
    item_rewards: Optional[List[str]] = None
    created_at: datetime
    objectives: List[QuestObjectiveResponse] = []

    @model_validator(mode="before")
    @classmethod
    def resolve_sqlalchemy_objectives(cls, data: Any) -> Any:
        if data and not isinstance(data, dict):
            attribs = {}
            for field in cls.model_fields.keys():
                if field == "objectives":
                    attribs["objectives"] = getattr(data, "objectives", [])
                elif hasattr(data, field):
                    attribs[field] = getattr(data, field)
            return attribs
        return data

    model_config = ConfigDict(from_attributes=True)

# Quest Progress Schemas
class QuestProgressCreate(BaseModel):
    player_id: Optional[str] = "default_player"
    quest_id: UUID

class QuestProgressResponse(BaseModel):
    id: UUID
    player_id: str
    quest_id: UUID
    quest_giver_slug: str
    status: str
    objectives_state: Dict[str, int]
    started_at: datetime
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class QuestProgressUpdate(BaseModel):
    player_id: Optional[str] = "default_player"
    quest_id: UUID
    objective_index: int = Field(..., ge=0)
    increment_amount: Optional[int] = Field(default=1, ge=1)


class QuestGenerateRequest(BaseModel):
    npc_slug: str = Field(..., min_length=1)
    player_id: Optional[str] = "default_player"
    player_level: int = Field(default=1, ge=1, le=100)


class QuestValidateRequest(BaseModel):
    npc_slug: Optional[str] = None
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    difficulty: Optional[str] = "Medium"
    objectives: List[Dict[str, Any]] = []
    rewards: Dict[str, Any] = {}
    branches: Optional[List[Dict[str, Any]]] = None
    consequences: Optional[List[Dict[str, Any]]] = None


class QuestValidationResponse(BaseModel):
    valid: bool
    reasons: List[str]


# Hint Schemas
class HintGenerateRequest(BaseModel):
    quest_id: UUID
    player_id: str = Field(..., min_length=1, description="Player identifier requesting the hint")
    hint_level: int = Field(..., ge=1, le=3, description="Requested hint level: 1 (subtle), 2 (medium), 3 (direct)")

class HintResponse(BaseModel):
    hint_level: int
    hint: str
    spoiler_level: str
    cache_status: str

class HintStatusResponse(BaseModel):
    quest_id: UUID
    player_id: str
    current_level: int
    last_requested_at: Optional[datetime] = None
    cooldown_remaining_seconds: int


class QuestReward(BaseModel):
    gold: int
    xp: int
    items: List[str] = []

    model_config = ConfigDict(from_attributes=True)


class QuestGeneratedResponse(BaseModel):
    api_version: str = "1.0"
    npc_slug: str
    title: str
    description: str
    difficulty: str
    rewards: QuestReward
    objectives: List[QuestObjectiveResponse]

    model_config = ConfigDict(from_attributes=True)


class ErrorDetail(BaseModel):
    code: str
    message: str
    retry_after_seconds: Optional[int] = None


class ErrorEnvelope(BaseModel):
    api_version: str = "1.0"
    error: ErrorDetail
