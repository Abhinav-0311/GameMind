import logging
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.npc import NPCProfile
from app.models.document import DocumentChunk
from app.schemas import DialogueAssembleRequest, DialogueAssembleResponse, RetrievedChunkMetadata

logger = logging.getLogger(__name__)

class DialogueService:
    @staticmethod
    def assemble_prompt(db: Session, request: DialogueAssembleRequest, history: Optional[List] = None) -> DialogueAssembleResponse:
        """
        Deterministic dialog prompt assembler.
        Retrieves the NPC, queries selected chunks, formats variables, and outputs telemetry metrics.
        """
        import time
        start_time = time.time()

        # 1. Lookup active NPC profile by slug
        npc = db.query(NPCProfile).filter(
            NPCProfile.slug == request.npc_slug,
            NPCProfile.deleted_at.is_(None)
        ).first()

        if not npc:
            raise ValueError(f"NPC profile with slug '{request.npc_slug}' not found or has been deleted.")

        warnings = []

        # 2. Player Input Truncation Check
        player_msg = request.player_message
        if len(player_msg) > 4000:
            truncated_len = len(player_msg)
            player_msg = player_msg[:4000]
            warnings.append(f"Player message truncated from {truncated_len} to 4000 characters.")

        # 3. Retrieve and Format Selected Chunks from DB
        ordered_chunks = []
        retrieved_chunks_meta = []
        
        if request.selected_chunk_ids:
            chunks = db.query(DocumentChunk).filter(DocumentChunk.id.in_(request.selected_chunk_ids)).all()
            chunk_map = {chunk.id: chunk for chunk in chunks}
            
            for cid in request.selected_chunk_ids:
                if cid in chunk_map:
                    ordered_chunks.append(chunk_map[cid])
            
            for chunk in ordered_chunks:
                retrieved_chunks_meta.append(
                    RetrievedChunkMetadata(
                        id=chunk.id,
                        document_id=chunk.document_id,
                        chunk_index=chunk.chunk_index,
                        character_count=len(chunk.content)
                    )
                )

        retrieved_parts = []
        current_len = 0
        truncated_lore = False

        for c in ordered_chunks:
            title = c.metadata_json.get("title", "Unknown Document") if c.metadata_json else "Unknown Document"
            part = f"Document: {title} (Chunk: #{c.chunk_index + 1})\nContent: {c.content}"
            
            if current_len + len(part) > 8000:
                remaining = 8000 - current_len
                if remaining > 0:
                    retrieved_parts.append(part[:remaining] + "... [TRUNCATED DUE TO CONTEXT LIMIT]")
                truncated_lore = True
                break
            
            retrieved_parts.append(part)
            current_len += len(part) + 2

        if truncated_lore:
            warnings.append("Retrieved lore chunks context truncated to 8000 characters.")

        if not retrieved_parts:
            retrieved_context = "No relevant lore chunks provided."
        else:
            retrieved_context = "\n\n".join(retrieved_parts)

        # 4. Formulate System Prompt
        title_clause = f", titled '{npc.title}'" if npc.title else ""
        system_prompt = (
            f"You are simulating the NPC character named '{npc.name}'{title_clause}.\n"
            "You must stay in character at all times, adopting the personality guidelines, dialogue style, and alignment of the character.\n"
            "Core Instructions:\n"
            "- Respond to player messages using the character's voice profile, dialogue directives, and background context.\n"
            "- Refuse unsupported claims: If the player asks about events, facts, or details not documented in the provided World Lore Context or NPC Memories, you must state that you do not know or refuse to answer. Do not hallucinate, make up facts, or assume details outside the provided contexts."
        )

        # 5. Formulate NPC Context block
        npc_context = (
            f"Character Name: {npc.name}\n"
            f"Title/Rank: {npc.title or 'n/a'}\n"
            f"Faction Alignment: {npc.faction_alignment or 'UNALIGNED'}\n"
            f"Personality Background: {npc.personality_summary}\n"
            f"Dialogue Style Guidelines: {npc.dialogue_style or 'n/a'}\n"
            f"Voice Identifier: {npc.voice_profile or 'n/a'}"
        )

        player_id = request.player_id or "default_player"

        # 5a. NPC Personality & Traits Block (Phase 8)
        from app.services.personality_engine import PersonalityEngine
        personality = PersonalityEngine.evaluate_personality(db, npc.slug)
        personality_lines = []
        traits = personality.get("traits", {})
        if traits:
            traits_str = ", ".join([f"{k}: {v}" for k, v in traits.items()])
            personality_lines.append(f"Traits: {traits_str}")
        tendencies = personality.get("behavioral_tendencies", {})
        if tendencies:
            tendencies_str = ", ".join([f"{k}: {v}" for k, v in tendencies.items()])
            personality_lines.append(f"Behavioral Tendencies: {tendencies_str}")
        preferences = personality.get("conversation_preferences", {})
        if preferences:
            prefs_str = ", ".join([f"{k}: {v}" for k, v in preferences.items()])
            personality_lines.append(f"Conversation Preferences: {prefs_str}")
        
        personality_lines = personality_lines[:10]  # MAX_PERSONALITY_LINES = 10
        personality_str = "\n".join(personality_lines)

        # 5b. NPC Emotion State Block (Phase 8)
        from app.services.emotion_engine import EmotionEngine
        emotions = EmotionEngine.get_emotional_state(db, npc.slug, player_id)
        emotion_str = (
            f"Trust: {emotions.get('trust', 50)}/100\n"
            f"Fear: {emotions.get('fear', 0)}/100\n"
            f"Anger: {emotions.get('anger', 0)}/100\n"
            f"Curiosity: {emotions.get('curiosity', 0)}/100\n"
            f"Loyalty: {emotions.get('loyalty', 0)}/100"
        )

        # 5c. NPC Conversation Plan Block (Phase 8)
        from app.services.conversation_planner import ConversationPlanner
        plan = ConversationPlanner.generate_plan(db, npc.slug, player_id, player_msg, history)
        plan_lines = []
        goals = plan.get("goals", [])[:5]  # MAX_CONVERSATION_GOALS = 5
        if goals:
            plan_lines.append("Conversation Goals:")
            for g in goals:
                plan_lines.append(f"- {g}")
        topics = plan.get("topic_priorities", [])
        matched_topics = [t["topic"] for t in topics if t["priority"] > 1]
        if matched_topics:
            plan_lines.append(f"Topic Priorities: {', '.join(matched_topics)}")
        plan_str = "\n".join(plan_lines)

        # 5d. Dialogue Directives Block (Phase 8)
        from app.services.dialogue_style_engine import DialogueStyleEngine
        directives = DialogueStyleEngine.get_directives(personality, emotions)[:8]  # MAX_DIRECTIVES = 8
        
        from app.services.telemetry_service import TelemetryService
        TelemetryService.record_narrative_metric(
            db,
            action_type="dialogue_style_directives_generated_total",
            npc_slug=npc.slug,
            model_used="dialogue_style_engine"
        )
        directives_str = "\n".join([f"- {d}" for d in directives])

        # 5e. Conversation Continuity Block (Phase 8)
        from app.services.conversation_continuity import ConversationContinuity
        conv_id = request.conversation_id if hasattr(request, "conversation_id") else None
        continuity_res = ConversationContinuity.analyze_continuity(db, conv_id, player_msg)
        hits = continuity_res.get("hits", [])[:5]  # MAX_CONTINUITY_REFERENCES = 5
        if hits:
            continuity_str = f"Recently discussed context/keywords to reference: {', '.join(hits)}"
        else:
            continuity_str = "No recent continuity references detected."

        # Retrieve matching NPC memories (dynamic episodic experiences)
        from app.services.gemini_service import GeminiService
        from app.services.rag_service import RAGService
        from app.services.memory_service import MemoryService
        
        gemini = GeminiService()
        rag = RAGService(gemini)
        mem_service = MemoryService(gemini, rag)
        retrieved_memories = mem_service.retrieve_memories(db, npc.id, player_msg, limit=5, player_id=player_id)

        # Retrieve relationship details
        from app.models.relationship import NPCRelationship
        rel = db.query(NPCRelationship).filter(
            NPCRelationship.npc_slug == npc.slug,
            NPCRelationship.player_id == player_id
        ).first()

        if not rel:
            trust, respect, friendship, fear = 50, 50, 50, 0
            last_reason = None
        else:
            trust, respect, friendship, fear = rel.trust, rel.respect, rel.friendship, rel.fear
            last_reason = rel.last_reason

        standing_label = DialogueService.get_standing_label(trust, respect, friendship, fear)
        
        relationship_lines = [
            f"Standing: {standing_label}",
            f"Trust: {trust}/100",
            f"Respect: {respect}/100",
            f"Friendship: {friendship}/100",
            f"Fear: {fear}/100"
        ]
        if last_reason:
            relationship_lines.append(f"Last Update Reason: {last_reason}")
        relationship_str = "\n".join(relationship_lines)

        # Retrieve active world state flags ordered by priority DESC, updated_at DESC
        from app.models.world_state import WorldStateFlag
        active_flags = db.query(WorldStateFlag).filter(
            WorldStateFlag.is_active == True
        ).order_by(
            WorldStateFlag.priority.desc(),
            WorldStateFlag.updated_at.desc()
        ).all()

        if not active_flags:
            world_state_str = "No active world events or environmental conditions."
        else:
            world_state_str = "\n".join([f"- {flag.flag_key}: {flag.flag_value}" for flag in active_flags])

        # Retrieve player quest progress sheets for this NPC
        from app.models.quest import Quest, QuestProgress
        active_quests = db.query(QuestProgress, Quest).join(Quest, Quest.id == QuestProgress.quest_id).filter(
            QuestProgress.player_id == player_id,
            QuestProgress.quest_giver_slug == npc.slug,
            QuestProgress.status == "active"
        ).all()

        completed_quests = db.query(QuestProgress, Quest).join(Quest, Quest.id == QuestProgress.quest_id).filter(
            QuestProgress.player_id == player_id,
            QuestProgress.quest_giver_slug == npc.slug,
            QuestProgress.status == "completed"
        ).order_by(QuestProgress.completed_at.desc()).limit(3).all()

        quest_lines = []
        for progress, quest in active_quests:
            from app.models.quest import QuestObjective
            objectives = db.query(QuestObjective).filter(QuestObjective.quest_id == quest.id).order_by(QuestObjective.objective_index).all()
            obj_strings = []
            for obj in objectives:
                idx_str = str(obj.objective_index)
                curr = progress.objectives_state.get(idx_str, 0)
                req = obj.quantity_required
                obj_strings.append(f"{obj.description}: {curr}/{req}")
            obj_details = ", ".join(obj_strings)
            quest_lines.append(f"* Active: {quest.title} ({obj_details})")

        for progress, quest in completed_quests:
            quest_lines.append(f"* Completed: {quest.title}")

        if not quest_lines:
            quest_str = "No active or completed quests with this NPC."
        else:
            quest_str = "\n".join(quest_lines)

        dialogue_session_parts = []
        if history:
            for msg in history:
                sender_label = npc.name if msg.sender == "npc" else "Player"
                dialogue_session_parts.append(f"{sender_label}: {msg.content}")
        
        dialogue_session_parts.append(f"Player: {player_msg}")
        dialogue_session_str = "\n".join(dialogue_session_parts)

        # Construct raw prompt parts for budget calculation
        raw_prompt_without_graph = (
            f"[System Instructions]\n{system_prompt}\n\n"
            f"[NPC Attributes]\n{npc_context}\n\n"
            f"[NPC Personality & Traits]\n{personality_str}\n\n"
            f"[NPC Emotion State]\n{emotion_str}\n\n"
            f"[NPC Conversation Plan]\n{plan_str}\n\n"
            f"[Dialogue Directives]\n{directives_str}\n\n"
            f"[Conversation Continuity]\n{continuity_str}\n\n"
            f"[NPC Memories]\n{retrieved_memories}\n\n"
            f"[NPC Quests]\n{quest_str}\n\n"
            f"[NPC Relationship]\n{relationship_str}\n\n"
            f"[World State Context]\n{world_state_str}\n\n"
            f"[World Lore Context]\n{retrieved_context}\n\n"
            f"[Dialogue Session]\n{dialogue_session_str}\n\n"
            f"{npc.name}:"
        )
        estimated_other_tokens = len(raw_prompt_without_graph) // 4
        remaining_budget = max(0, 1024 - estimated_other_tokens)

        # Retrieve graph context using ContextAssemblerService
        graph_context_str = ""
        try:
            from app.services.graph_traversal import graph_traversal_service
            from app.services.context_assembler import context_assembler_service
            
            subgraph_res = graph_traversal_service.get_subgraph(
                db=db,
                seeds=[npc.slug],
                depth=2
            )
            graph_context_str = context_assembler_service.assemble_context(
                db=db,
                subgraph_results=subgraph_res,
                token_budget=remaining_budget
            )
        except Exception as ex:
            logger.error(f"Failed to assemble graph context for dialogue: {ex}")

        graph_block = f"{graph_context_str}\n\n" if graph_context_str else ""

        assembled_prompt = (
            f"[System Instructions]\n"
            f"{system_prompt}\n\n"
            f"[NPC Attributes]\n"
            f"{npc_context}\n\n"
            f"[NPC Personality & Traits]\n"
            f"{personality_str}\n\n"
            f"[NPC Emotion State]\n"
            f"{emotion_str}\n\n"
            f"[NPC Conversation Plan]\n"
            f"{plan_str}\n\n"
            f"[Dialogue Directives]\n"
            f"{directives_str}\n\n"
            f"[Conversation Continuity]\n"
            f"{continuity_str}\n\n"
            f"[NPC Memories]\n"
            f"{retrieved_memories}\n\n"
            f"[NPC Quests]\n"
            f"{quest_str}\n\n"
            f"[NPC Relationship]\n"
            f"{relationship_str}\n\n"
            f"[World State Context]\n"
            f"{world_state_str}\n\n"
            f"{graph_block}"
            f"[World Lore Context]\n"
            f"{retrieved_context}\n\n"
            f"[Dialogue Session]\n"
            f"{dialogue_session_str}\n\n"
            f"{npc.name}:"
        )

        character_count = len(assembled_prompt)
        estimated_tokens = character_count // 4

        # Record Telemetry Metrics after assembly completes
        duration_ms = int((time.time() - start_time) * 1000)
        
        TelemetryService.record_narrative_metric(
            db,
            action_type="dialogue_prompt_sections_generated_total",
            npc_slug=npc.slug,
            model_used="dialogue_service"
        )
        TelemetryService.record_narrative_metric(
            db,
            action_type="dialogue_assembly_duration_seconds",
            npc_slug=npc.slug,
            model_used="dialogue_service",
            latency_ms=duration_ms
        )
        TelemetryService.record_narrative_metric(
            db,
            action_type="dialogue_assembled_tokens_total",
            npc_slug=npc.slug,
            model_used="dialogue_service",
            input_tokens=estimated_tokens
        )
        
        # Calculate messages scanned
        from app.models.session import Message as SessionMessage
        scanned_count = 0
        if conv_id:
            scanned_count = db.query(SessionMessage).filter(SessionMessage.conversation_id == conv_id).count()
            scanned_count = min(50, scanned_count)
            
        TelemetryService.record_narrative_metric(
            db,
            action_type="dialogue_history_messages_scanned_total",
            npc_slug=npc.slug,
            model_used="dialogue_service",
            input_tokens=scanned_count
        )

        return DialogueAssembleResponse(
            npc_slug=npc.slug,
            player_message=player_msg,
            system_prompt=system_prompt,
            npc_context=npc_context,
            retrieved_context=retrieved_context,
            assembled_prompt=assembled_prompt,
            prompt_version="v1",
            character_count=character_count,
            estimated_tokens=estimated_tokens,
            retrieved_chunk_count=len(retrieved_chunks_meta),
            retrieved_chunks=retrieved_chunks_meta,
            warnings=warnings
        )

    @staticmethod
    def get_standing_label(trust: int, respect: int, friendship: int, fear: int) -> str:
        if fear >= 60:
            return "Feared Figure"
        elif trust >= 70 and respect >= 60:
            return "Trusted Ally"
        elif friendship >= 70:
            return "Close Friend"
        elif respect >= 75:
            return "Respected Hero"
        elif trust <= 30:
            return "Distrusted"
        else:
            return "Neutral"

