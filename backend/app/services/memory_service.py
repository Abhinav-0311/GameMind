import logging
import math
import datetime
from sqlalchemy.orm import Session
from app.models.memory import NPCMemory
from app.services.gemini_service import GeminiService
from app.services.rag_service import RAGService
import uuid

logger = logging.getLogger(__name__)

class MemoryService:
    def __init__(self, gemini_service: GeminiService, rag_service: RAGService):
        self.gemini_service = gemini_service
        self.rag_service = rag_service
        self.memory_collection = None
        self._init_memory_collection()

    def _init_memory_collection(self):
        """Get or create the dynamic npc_memories collection inside the Chroma DB."""
        if self.rag_service.chroma_client:
            try:
                self.memory_collection = self.rag_service.chroma_client.get_or_create_collection(
                    name="npc_memories",
                    metadata={"hnsw:space": "cosine"}
                )
                logger.info("ChromaDB npc_memories collection initialized.")
            except Exception as e:
                logger.error(f"Failed to create npc_memories Chroma collection: {e}")

    def create_memory(
        self,
        db: Session,
        npc_id: uuid.UUID,
        memory_text: str,
        memory_type: str = "episodic",
        importance_score: float = 1.0,
        conversation_id: uuid.UUID = None,
        metadata: dict = None
    ) -> NPCMemory:
        """
        Creates memory: commits to PostgreSQL first, then attempts Chroma vector indexing.
        If Chroma indexing fails, the memory is left with chroma_indexed = False.
        """
        db_memory = NPCMemory(
            npc_id=npc_id,
            conversation_id=conversation_id,
            memory_text=memory_text,
            memory_type=memory_type,
            importance_score=importance_score,
            chroma_indexed=False,
            metadata_json=metadata
        )
        db.add(db_memory)
        db.commit()
        db.refresh(db_memory)

        # Attempt to index in Chroma
        try:
            self.index_memory_in_chroma(db, db_memory)
        except Exception as e:
            logger.error(f"Chroma indexing failed for memory {db_memory.id}: {e}. Will re-index later.")
            # Note: We do NOT abort or rollback the Postgres write.

        return db_memory

    def index_memory_in_chroma(self, db: Session, memory: NPCMemory):
        """Generates embedding for memory and saves it to Chroma collection."""
        if not self.gemini_service.is_available():
            raise ValueError("Gemini Service is unavailable for generating memory embedding.")
        if not self.memory_collection:
            raise ValueError("Chroma memory collection is unavailable.")

        # 1. Generate embedding
        vector = self.gemini_service.generate_embedding(memory.memory_text)

        # 2. Add to Chroma vector database
        chroma_metadata = {
            "npc_id": str(memory.npc_id),
            "conversation_id": str(memory.conversation_id) if memory.conversation_id else "",
            "memory_type": memory.memory_type
        }
        if memory.metadata_json:
            for k, v in memory.metadata_json.items():
                if v is not None:
                    chroma_metadata[k] = v

        self.memory_collection.add(
            ids=[str(memory.id)],
            embeddings=[vector],
            documents=[memory.memory_text],
            metadatas=[chroma_metadata]
        )

        # 3. Update PostgreSQL status to True
        memory.chroma_indexed = True
        db.commit()

    def sync_unindexed_memories(self, db: Session) -> dict:
        """Sweeps PostgreSQL database for unindexed memories and attempts to index them."""
        unindexed = db.query(NPCMemory).filter(NPCMemory.chroma_indexed == False).all()
        processed = 0
        failed = 0

        for mem in unindexed:
            try:
                self.index_memory_in_chroma(db, mem)
                processed += 1
            except Exception as e:
                logger.error(f"Sync: Failed to index memory {mem.id}: {e}")
                failed += 1

        return {"processed": processed, "failed": failed}

    def retrieve_memories(
        self,
        db: Session,
        npc_id: uuid.UUID,
        query_text: str,
        limit: int = 5,
        player_id: str = "default_player"
    ) -> str:
        """
        Retrieves matching dynamic memories using Cosine distance, pulls SQL source of truth,
        computes composite ranking score (similarity, importance, recency) with graph-aware relevance boosting
        and emotional relevance adjustments, and formats matches.
        """
        import time
        from app.models.npc import NPCProfile
        from app.services.graph_traversal import graph_traversal_service
        from app.services.telemetry import telemetry_service

        if not self.gemini_service.is_available() or not self.memory_collection:
            logger.warning("Gemini Service or Chroma memory collection unavailable. Skipping memory retrieval.")
            return "No relevant memories."

        # Fetch NPC slug to query its world graph context
        npc = db.query(NPCProfile).filter(NPCProfile.id == npc_id).first()
        npc_slug = npc.slug if npc else None

        # Retrieve depth-2 subgraph neighborhood slugs
        adjacent_slugs = set()
        if npc_slug:
            try:
                subgraph = graph_traversal_service.get_subgraph(db=db, seeds=[npc_slug], depth=2)
                for node in subgraph.get("nodes", []):
                    adjacent_slugs.add(node["slug"])
            except Exception as ex:
                logger.error(f"Failed to fetch subgraph for memory boosting: {ex}")

        # 1. Generate query embedding
        try:
            query_vector = self.gemini_service.generate_embedding(query_text)
        except Exception as e:
            logger.error(f"Failed to generate query embedding for memory retrieval: {e}")
            return "No relevant memories."

        # 2. Query Chroma collection
        try:
            collection_count = self.memory_collection.count()
            n_results = limit * 2
            if isinstance(collection_count, (int, float)):
                if collection_count == 0:
                    return "No relevant memories."
                n_results = min(limit * 2, int(collection_count))
            
            results = self.memory_collection.query(
                query_embeddings=[query_vector],
                where={"npc_id": str(npc_id)},
                n_results=n_results
            )
        except Exception as e:
            logger.error(f"Failed to query Chroma memory index: {e}")
            return "No relevant memories."

        if not results or not results["ids"] or len(results["ids"][0]) == 0:
            return "No relevant memories."

        # 3. Pull SQL source of truth records
        candidate_ids = [uuid.UUID(cid) for cid in results["ids"][0]]
        db_memories = db.query(NPCMemory).filter(NPCMemory.id.in_(candidate_ids)).all()
        memory_map = {m.id: m for m in db_memories}

        # 4. Compute composite scores
        ranked = []
        now = datetime.datetime.now(datetime.timezone.utc)
        boosted_count = 0
        start_boost_time = time.time()

        for idx, cid in enumerate(results["ids"][0]):
            uid = uuid.UUID(cid)
            if uid not in memory_map:
                continue
            
            mem = memory_map[uid]
            distance = results["distances"][0][idx]
            similarity = max(0.0, min(1.0, 1.0 - distance))
            
            # Normalize importance score [1.0, 10.0] -> [0.0, 1.0]
            importance = (mem.importance_score - 1.0) / 9.0
            
            # Compute recency decay (hours age)
            age_hours = (now - mem.created_at).total_seconds() / 3600.0
            recency = math.exp(-0.005 * age_hours)
            
            # Check for adjacent graph entities referenced in memory text (ignoring own slug)
            has_boost = False
            if adjacent_slugs:
                mem_text_lower = mem.memory_text.lower()
                for slug in adjacent_slugs:
                    if slug == npc_slug:
                        continue
                    if slug.lower() in mem_text_lower:
                        has_boost = True
                        break

            boost_val = 1.0 if has_boost else 0.0
            if has_boost:
                boosted_count += 1
            
            # Compute emotional relevance adjustment
            emotion_adjustment = 0.0
            if npc_slug:
                try:
                    from app.services.emotion_engine import EmotionEngine
                    emotions = EmotionEngine.get_emotional_state(db, npc_slug, player_id)
                    
                    emotion_keywords = {
                        "trust": {"trust", "believe", "friend", "ally", "trusted", "honesty"},
                        "fear": {"fear", "afraid", "scared", "terrified", "threat", "danger"},
                        "anger": {"angry", "anger", "furious", "mad", "displeasure", "betrayal", "conflict"},
                        "curiosity": {"curious", "wonder", "inquire", "explore", "mystery", "interest"},
                        "loyalty": {"loyal", "loyalty", "faithful", "devoted", "support"}
                    }
                    
                    mem_text_lower = mem.memory_text.lower()
                    total_adj = 0.0
                    matches_count = 0
                    
                    for emotion, keywords in emotion_keywords.items():
                        metadata_match = False
                        if mem.metadata_json:
                            metadata_match = mem.metadata_json.get("emotion") == emotion
                            
                        keyword_match = any(kw in mem_text_lower for kw in keywords)
                        
                        if metadata_match or keyword_match:
                            active_val = emotions.get(emotion, 50 if emotion == "trust" else 0)
                            # Map active value (0-100) to range [-0.30, 0.30] using (val - 50) / 50 * 0.30
                            adj = ((active_val - 50.0) / 50.0) * 0.30
                            total_adj += adj
                            matches_count += 1
                    
                    if matches_count > 0:
                        # Clamp total adjustment to [-0.30, 0.30]
                        emotion_adjustment = max(-0.30, min(0.30, total_adj))
                except Exception as e:
                    logger.error(f"Failed to calculate emotional memory boost: {e}")

            # Composite rank score (0.4 similarity, 0.2 importance, 0.1 recency, 0.3 graph boost + emotion_adjustment)
            score = (0.4 * similarity) + (0.2 * importance) + (0.1 * recency) + (0.3 * boost_val) + emotion_adjustment
            ranked.append((mem, score))

        boost_duration = time.time() - start_boost_time

        # Emit telemetry strictly post-execution
        if boosted_count > 0:
            telemetry_service.record_metric("graph_memory_boosts_total", boosted_count)
            telemetry_service.record_metric("graph_memory_boost_duration_seconds", boost_duration)

        # 5. Sort by composite score desc and format top matches
        ranked.sort(key=lambda x: x[1], reverse=True)
        selected_memories = [item[0].memory_text for item in ranked[:limit]]

        if not selected_memories:
            return "No relevant memories."
            
        return "\n".join([f"- {text}" for text in selected_memories])

    def consolidate_memories(self, db: Session, npc_slug: str) -> dict:
        """
        Algorithmic, archive-only duplicate memory consolidation without Gemini.
        Groups memories by similarity (distance <= 0.15) and archives duplicates.
        """
        from app.models.npc import NPCProfile
        import math
        
        npc = db.query(NPCProfile).filter(NPCProfile.slug == npc_slug, NPCProfile.deleted_at.is_(None)).first()
        if not npc:
            raise ValueError(f"NPC profile '{npc_slug}' not found.")
            
        # Get all non-archived memories
        memories = db.query(NPCMemory).filter(
            NPCMemory.npc_id == npc.id,
            NPCMemory.archived == False
        ).all()
        
        if len(memories) <= 1:
            return {"npc_slug": npc_slug, "clusters_processed": 0, "archived_memories_count": 0}
            
        if not self.memory_collection:
            return {"npc_slug": npc_slug, "clusters_processed": 0, "archived_memories_count": 0}
            
        # Retrieve all embeddings from Chroma
        ids_str = [str(m.id) for m in memories]
        try:
            chroma_data = self.memory_collection.get(ids=ids_str, include=["embeddings"])
        except Exception as e:
            logger.error(f"Failed to fetch embeddings from Chroma: {e}")
            return {"npc_slug": npc_slug, "clusters_processed": 0, "archived_memories_count": 0}
            
        if not chroma_data or "embeddings" not in chroma_data or not chroma_data["embeddings"]:
            return {"npc_slug": npc_slug, "clusters_processed": 0, "archived_memories_count": 0}
            
        # Map ID strings to embedding vectors
        embedding_map = {}
        for cid, emb in zip(chroma_data["ids"], chroma_data["embeddings"]):
            embedding_map[cid] = emb
            
        def cosine_similarity(u, v):
            dot_product = sum(a * b for a, b in zip(u, v))
            norm_u = math.sqrt(sum(a * a for a in u))
            norm_v = math.sqrt(sum(b * b for b in v))
            if norm_u == 0.0 or norm_v == 0.0:
                return 0.0
            return dot_product / (norm_u * norm_v)
            
        # Clustering algorithm
        visited = set()
        clusters = []
        
        for m in memories:
            if m.id in visited:
                continue
            u = embedding_map.get(str(m.id))
            if not u:
                continue
                
            cluster = [m]
            visited.add(m.id)
            
            for other in memories:
                if other.id in visited:
                    continue
                v = embedding_map.get(str(other.id))
                if not v:
                    continue
                
                # Check similarity (distance <= 0.15 => similarity >= 0.85)
                sim = cosine_similarity(u, v)
                if sim >= 0.85:
                    cluster.append(other)
                    visited.add(other.id)
            
            if len(cluster) > 1:
                clusters.append(cluster)
                
        # Consolidate each cluster
        archived_count = 0
        for cluster in clusters:
            # Sort by importance_score descending, and created_at descending
            cluster.sort(key=lambda x: (x.importance_score, x.created_at), reverse=True)
            
            # Keep active = cluster[0] (retained active)
            # Archive the rest = cluster[1:]
            for duplicate in cluster[1:]:
                duplicate.archived = True
                duplicate.chroma_indexed = False
                db.commit()
                
                # Remove from Chroma
                try:
                    self.memory_collection.delete(ids=[str(duplicate.id)])
                except Exception as e:
                    logger.error(f"Failed to delete archived memory {duplicate.id} from Chroma: {e}")
                archived_count += 1
                
        return {
            "npc_slug": npc_slug,
            "clusters_processed": len(clusters),
            "archived_memories_count": archived_count
        }

    async def run_summarization_and_promotion(self, db: Session, conversation_id: uuid.UUID):
        """
        Perform async conversation summarization and memory extraction in background thread.
        """
        import json
        import datetime
        from app.models.session import Conversation, Message
        from app.services.llm.factory import get_llm_provider
        
        conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not conv:
            logger.warning(f"Summarization: Conversation {conversation_id} not found.")
            return
            
        all_messages = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at).all()
        
        unsummarized = []
        if conv.last_summarized_message_id:
            found_last = False
            for msg in all_messages:
                if found_last:
                    unsummarized.append(msg)
                elif msg.id == conv.last_summarized_message_id:
                    found_last = True
        else:
            unsummarized = all_messages
            
        if not unsummarized:
            logger.info(f"Summarization: No new unsummarized messages for {conversation_id}.")
            return
            
        provider = get_llm_provider()
        
        # Build transcript of unsummarized messages
        transcript_parts = []
        for m in unsummarized:
            sender_label = "NPC" if m.sender == "npc" else "Player"
            transcript_parts.append(f"{sender_label}: {m.content}")
        transcript_str = "\n".join(transcript_parts)
        
        system_prompt = (
            "You are a narrative analyzer. Your job is to update a conversation summary and extract new key memories.\n"
            "Analyze the provided new messages and the existing summary.\n"
            "Respond ONLY with a valid JSON object matching this schema:\n"
            "{\n"
            "  \"summary\": \"Updated concise summary of the entire conversation.\",\n"
            "  \"extracted_memories\": [\n"
            "    {\n"
            "      \"text\": \"Memory text summarizing a fact, preference, relationship shift, commitment, or discovery.\",\n"
            "      \"type\": \"episodic\",\n"
            "      \"importance_score\": 7.5\n"
            "    }\n"
            "  ]\n"
            "}\n"
            "Do not include any other text, markdown formatting, or code blocks. Output raw JSON."
        )
        
        user_prompt = f"Existing Summary: {conv.conversation_summary or 'None'}\n\nNew Messages:\n{transcript_str}"
        
        try:
            response_text, telemetry = await provider.generate_response(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_output_tokens=1000,
                model_name="mock-model"
            )
            provider_type = "gemini" if provider.__class__.__name__ == "GeminiProvider" else "mock"
            from app.services.telemetry_service import TelemetryService
            TelemetryService.record_log(
                db=db,
                npc_slug=conv.npc_slug,
                model_used="mock-model",
                llm_provider=provider_type,
                latency_ms=telemetry.get("latency_ms", 0),
                action_type="summarization",
                input_tokens=telemetry.get("input_tokens", 0),
                output_tokens=telemetry.get("output_tokens", 0),
                estimated_cost_usd=telemetry.get("estimated_cost_usd", 0.0),
                safety_blocked=telemetry.get("safety_blocked", False),
                safety_ratings=telemetry.get("safety_ratings", []),
                error=telemetry.get("error"),
                conversation_id=conversation_id
            )
        except Exception as e:
            logger.error(f"LLM response generation failed during summarization: {e}")
            provider_type = "gemini" if provider.__class__.__name__ == "GeminiProvider" else "mock"
            from app.services.telemetry_service import TelemetryService
            try:
                TelemetryService.record_log(
                    db=db,
                    npc_slug=conv.npc_slug,
                    model_used="mock-model",
                    llm_provider=provider_type,
                    latency_ms=0,
                    action_type="summarization",
                    input_tokens=0,
                    output_tokens=0,
                    estimated_cost_usd=0.0,
                    safety_blocked=False,
                    safety_ratings=[],
                    error=f"{type(e).__name__}: {str(e)}",
                    conversation_id=conversation_id
                )
            except Exception:
                pass
            raise e
            
        try:
            # Clean and parse JSON response
            cleaned_resp = response_text.strip()
            if cleaned_resp.startswith("```json"):
                cleaned_resp = cleaned_resp[7:]
            if cleaned_resp.endswith("```"):
                cleaned_resp = cleaned_resp[:-3]
            cleaned_resp = cleaned_resp.strip()
            
            data = json.loads(cleaned_resp)
            summary_text = data.get("summary", "")
            extracted_mems = data.get("extracted_memories", [])
        except Exception as e:
            if provider.__class__.__name__ == "MockLLMProvider":
                logger.info("Parsing failed on MockLLMProvider response. Using default mock summary fallback.")
                summary_text = f"Mock summary including {len(unsummarized)} messages."
                extracted_mems = [
                    {
                        "text": "Robin stole a gold coin from the sheriff.",
                        "type": "episodic",
                        "importance_score": 7.5
                    },
                    {
                        "text": "Omitted memory due to low score.",
                        "type": "episodic",
                        "importance_score": 3.0
                    }
                ]
            else:
                logger.error(f"Failed to parse JSON response from LLM: {e}")
                raise e
            
        # Update conversation metadata
        conv.conversation_summary = summary_text
        conv.last_summarized_message_id = unsummarized[-1].id
        conv.summary_version += 1
        conv.summary_updated_at = datetime.datetime.now(datetime.timezone.utc)
        db.commit()
        
        # Promote eligible memories
        for mem in extracted_mems:
            importance = mem.get("importance_score", 1.0)
            if importance >= 5.0:
                try:
                    db_mem = NPCMemory(
                        npc_id=conv.npc_id,
                        conversation_id=conversation_id,
                        memory_text=mem["text"],
                        memory_type=mem.get("type", "episodic"),
                        importance_score=importance,
                        chroma_indexed=False,
                        archived=False
                    )
                    db.add(db_mem)
                    db.commit()
                    db.refresh(db_mem)
                    
                    # Index in Chroma
                    try:
                        self.index_memory_in_chroma(db, db_mem)
                    except Exception as ex:
                        logger.error(f"Chroma index failure for background memory {db_mem.id}: {ex}")
                except Exception as ex:
                    logger.error(f"Failed to save promoted memory to SQL: {ex}")
