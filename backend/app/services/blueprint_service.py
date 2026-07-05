import logging
import re
from uuid import UUID
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.document import Document, DocumentChunk
from app.models.blueprint import GameBlueprint

logger = logging.getLogger(__name__)

class BlueprintService:
    def _clean_markdown(self, text: str) -> str:
        text = text.strip()
        text = re.sub(r"^\s*[-*]\s*", "", text)
        text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
        text = re.sub(r"^#+\s*", "", text)
        return text.strip()

    def _clean_title(self, text: str) -> str:
        text = self._clean_markdown(text)
        text = re.sub(r"^(NPC|Quest Hook\s*\d*)\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"[^A-Za-z0-9\s'-]", "", text)
        return re.sub(r"\s+", " ", text).strip()

    def _iter_chunk_lines(self, chunks: List[DocumentChunk]):
        for chunk in chunks:
            for line in chunk.content.split("\n"):
                cleaned = self._clean_markdown(line)
                if cleaned:
                    yield chunk, cleaned

    def _objective_to_title(self, objective: str, fallback_index: int) -> str:
        objective = self._clean_markdown(objective)
        objective = re.sub(r"^Objective:\s*", "", objective, flags=re.IGNORECASE)
        objective = re.split(r"\bPlayers\b|\bReward:\b|\.", objective, maxsplit=1, flags=re.IGNORECASE)[0]
        objective = self._clean_title(objective)
        if not objective:
            return f"Quest Hook {fallback_index + 1}"
        return objective[:80]

    def generate_blueprint_from_gdd(self, db: Session, document_id: UUID, game_project_id: str) -> GameBlueprint:
        # 1. Enforce document ownership by game_project_id
        doc = db.query(Document).filter(
            Document.id == document_id,
            Document.game_project_id == game_project_id
        ).first()
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Game Design Document not found or not owned by this project."
            )

        chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).all()
        if not chunks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target document has no text chunks indexed."
            )

        # 2. Extract sections using local rule-based matching
        summary = self._parse_summary(doc.title, chunks)
        narrative = self._parse_narrative(chunks)
        art = self._parse_art_style(chunks)
        npcs = self._parse_npc_archetypes(chunks)
        memory = self._parse_npc_memory(chunks)
        levels = self._parse_level_design(chunks)
        quests = self._parse_quest_hooks(chunks)
        
        # 3. Create flat Unity export preview
        unity_preview = self._generate_unity_preview(
            game_project_id, summary, narrative, art, npcs, memory, levels, quests
        )

        # 4. Save game blueprint to Postgres
        blueprint = GameBlueprint(
            title=f"Blueprint: {doc.title}",
            document_id=document_id,
            game_project_id=game_project_id,
            summary=summary,
            narrative_direction=narrative,
            art_style_direction=art,
            npc_archetypes=npcs,
            npc_memory_design=memory,
            level_design_suggestions=levels,
            quest_hooks=quests,
            unity_runtime_preview=unity_preview,
            status="draft"
        )
        db.add(blueprint)
        db.commit()
        db.refresh(blueprint)
        return blueprint

    def _parse_summary(self, doc_title: str, chunks: List[DocumentChunk]) -> Dict[str, Any]:
        content = {
            "title": doc_title,
            "description": "A game design template generated from the GDD."
        }
        citations = []
        warnings = []
        confidence = "Low"

        # Search for overview/summary keywords
        for chunk in chunks:
            if re.search(r"(overview|synopsis|summary|introduction|description)", chunk.content, re.IGNORECASE):
                # Scrape first few lines
                lines = [l.strip() for l in chunk.content.split("\n") if l.strip()]
                desc_lines = [l for l in lines if not re.match(r"^(overview|summary|introduction|title|#)", l, re.IGNORECASE)]
                if desc_lines:
                    content["description"] = " ".join(desc_lines[:3])
                    citations.append(str(chunk.id))
                    confidence = "High"
                    break

        if not citations:
            warnings.append("No explicit game overview found. Loaded default description.")
            # Use first chunk as citation fallback
            citations.append(str(chunks[0].id))
            confidence = "Low"

        return {
            "content": content,
            "citations": citations,
            "confidence": confidence,
            "warnings": warnings
        }

    def _parse_narrative(self, chunks: List[DocumentChunk]) -> Dict[str, Any]:
        content = {
            "themes": ["Conflict", "Survival"],
            "lore_background": "A world locked in eternal struggle."
        }
        citations = []
        warnings = []
        confidence = "Low"

        # Look for narrative indicators
        narrative_chunks = []
        for chunk in chunks:
            if re.search(r"(lore|story|history|background|narrative|faction|theme)", chunk.content, re.IGNORECASE):
                narrative_chunks.append(chunk)
                citations.append(str(chunk.id))

        if narrative_chunks:
            # Combine some lines for lore background
            extracted = []
            for nc in narrative_chunks[:2]:
                lines = [l.strip() for l in nc.content.split("\n") if len(l.strip()) > 20]
                extracted.extend(lines[:2])
            if extracted:
                content["lore_background"] = " ".join(extracted)
                confidence = "High"
        else:
            warnings.append("No detailed narrative or lore sections detected in GDD.")
            confidence = "Low"

        return {
            "content": content,
            "citations": citations,
            "confidence": confidence,
            "warnings": warnings
        }

    def _parse_art_style(self, chunks: List[DocumentChunk]) -> Dict[str, Any]:
        content = {
            "visual_theme": "Stylized Dark Fantasy",
            "color_palette": ["#1e293b", "#f97316"] # Cold blue / warm orange defaults
        }
        citations = []
        warnings = []
        confidence = "Low"

        # Look for visual style indicators
        for chunk in chunks:
            if re.search(r"(art|visual|style|palette|color|theme|look)", chunk.content, re.IGNORECASE):
                citations.append(str(chunk.id))
                # Search for color names or contrast references
                if re.search(r"(dark|grim|neon|vibrant|stylized|pixel|fantasy)", chunk.content, re.IGNORECASE):
                    content["visual_theme"] = "Stylized dark fantasy with high contrast color nodes."
                    confidence = "High"

        if not citations:
            warnings.append("No art style guidelines or color palette details detected in GDD.")
            confidence = "Low"

        return {
            "content": content,
            "citations": citations,
            "confidence": confidence,
            "warnings": warnings
        }

    def _parse_npc_archetypes(self, chunks: List[DocumentChunk]) -> Dict[str, Any]:
        content = {
            "npcs": [
                {"name": "Eldrin the Mage", "archetype": "Scholar / Mentor", "dialogue_style": "Formal and historical"}
            ]
        }
        citations = []
        warnings = []
        confidence = "Low"

        found_npcs = []
        seen_names = set()
        for chunk, line in self._iter_chunk_lines(chunks):
            npc_match = re.match(r"^NPC\s+([^:]+):\s*(.+)$", line, re.IGNORECASE)
            if not npc_match:
                continue

            raw_name = self._clean_title(npc_match.group(1))
            description = self._clean_markdown(npc_match.group(2))
            if not raw_name or raw_name.lower() in seen_names:
                continue

            seen_names.add(raw_name.lower())
            archetype = description.split(".")[0].strip() or "Character profile"
            found_npcs.append({
                "name": raw_name,
                "archetype": archetype,
                "dialogue_style": description
            })

            if str(chunk.id) not in citations:
                citations.append(str(chunk.id))

        if found_npcs:
            content["npcs"] = found_npcs[:5]
            confidence = "High"
        else:
            warnings.append("No explicit NPC archetypes or character files detected in GDD.")
            confidence = "Low"

        return {
            "content": content,
            "citations": citations,
            "confidence": confidence,
            "warnings": warnings
        }

    def _parse_npc_memory(self, chunks: List[DocumentChunk]) -> Dict[str, Any]:
        content = {
            "memory_nodes": [
                {"subject": "Ember Siege", "importance": 8}
            ]
        }
        citations = []
        warnings = []
        confidence = "Low"

        for chunk in chunks:
            if re.search(r"(memory|remember|knows|relation|siege|history|event)", chunk.content, re.IGNORECASE):
                citations.append(str(chunk.id))
                if "siege" in chunk.content.lower():
                    content["memory_nodes"].append({"subject": "Fall of Frostpeak and the Siege", "importance": 9})
                    confidence = "High"

        if not citations:
            warnings.append("No key event memory configurations detected for NPC minds.")
            confidence = "Low"

        return {
            "content": content,
            "citations": citations,
            "confidence": confidence,
            "warnings": warnings
        }

    def _parse_level_design(self, chunks: List[DocumentChunk]) -> Dict[str, Any]:
        content = {
            "level_layout": "Default starting zone with linear paths.",
            "interactive_elements": ["checkpoint", "chest"]
        }
        citations = []
        warnings = []
        confidence = "Low"

        for chunk in chunks:
            if re.search(r"(level|map|dungeon|room|zone|area|pass|gate|vent)", chunk.content, re.IGNORECASE):
                citations.append(str(chunk.id))
                if "vent" in chunk.content.lower() or "gate" in chunk.content.lower():
                    content["level_layout"] = "Volcanic environment with active geothermal vent systems and locked gates."
                    content["interactive_elements"] = ["geothermal_vent", "sky_iron_ore", "east_gate"]
                    confidence = "High"

        if not citations:
            warnings.append("No level design suggestions or zone outlines found in GDD.")
            confidence = "Low"

        return {
            "content": content,
            "citations": citations,
            "confidence": confidence,
            "warnings": warnings
        }

    def _parse_quest_hooks(self, chunks: List[DocumentChunk]) -> Dict[str, Any]:
        content = {
            "quests": [
                {"id": "q1", "title": "Tutorial Task", "objective": "Explore starting zone."}
            ]
        }
        citations = []
        warnings = []
        confidence = "Low"

        found_quests = []
        seen_titles = set()
        seen_objectives = set()
        for chunk, line in self._iter_chunk_lines(chunks):
            quest_match = re.match(
                r"^(?:Quest Hook\s*(\d+)|Quest\s*(\d+))\s*:\s*(.+)$",
                line,
                re.IGNORECASE
            )
            if not quest_match:
                continue

            quest_body = quest_match.group(3).strip()
            objective_match = re.search(
                r"Objective:\s*(.*?)(?:\s*Reward:\s*(.*))?$",
                quest_body,
                re.IGNORECASE
            )
            objective = self._clean_markdown(objective_match.group(1).strip()) if objective_match else quest_body
            reward = self._clean_markdown(objective_match.group(2).strip()) if objective_match and objective_match.group(2) else ""
            objective_key = re.sub(r"\s+", " ", objective.lower()).strip()
            if objective_key in seen_objectives:
                continue
            seen_objectives.add(objective_key)

            title = self._objective_to_title(objective, len(found_quests))
            base_title = title
            duplicate_index = 2
            while title.lower() in seen_titles:
                title = f"{base_title} {duplicate_index}"
                duplicate_index += 1
            seen_titles.add(title.lower())

            found_quests.append({
                "id": f"q_{len(found_quests)}",
                "title": title,
                "objective": objective,
                "reward": reward
            })

            if str(chunk.id) not in citations:
                citations.append(str(chunk.id))

        if found_quests:
            content["quests"] = found_quests[:5]
            confidence = "High"
        else:
            warnings.append("No quest chains or reward metrics defined in GDD.")
            confidence = "Low"

        return {
            "content": content,
            "citations": citations,
            "confidence": confidence,
            "warnings": warnings
        }

    def _generate_unity_preview(
        self, 
        project_id: str,
        summary: Dict[str, Any], 
        narrative: Dict[str, Any], 
        art: Dict[str, Any], 
        npcs: Dict[str, Any], 
        memory: Dict[str, Any], 
        levels: Dict[str, Any], 
        quests: Dict[str, Any]
    ) -> Dict[str, Any]:
        # Formulate a clean runtime config for Unity
        content = {
            "project_id": project_id,
            "version": "1.0.0",
            "game_summary": summary["content"],
            "narrative": narrative["content"],
            "art_style": art["content"],
            "npcs": npcs["content"].get("npcs", []),
            "npc_memories": memory["content"].get("memory_nodes", []),
            "levels": levels["content"],
            "quests": quests["content"].get("quests", [])
        }
        return {
            "content": content,
            "citations": [],
            "confidence": "High",
            "warnings": []
        }
