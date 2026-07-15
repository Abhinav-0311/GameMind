import logging
import re
from typing import Any, Dict, Iterable, List, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.blueprint import GameBlueprint
from app.models.document import Document, DocumentChunk

logger = logging.getLogger(__name__)


class BlueprintService:
    """Creates source-grounded blueprints with deterministic local extraction rules."""

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

    def _iter_chunk_lines(self, chunks: List[DocumentChunk]) -> Iterable[Tuple[DocumentChunk, str]]:
        for chunk in chunks:
            for line in chunk.content.split("\n"):
                cleaned = self._clean_markdown(line)
                if cleaned:
                    yield chunk, cleaned

    def _iter_chunk_lines_with_heading(self, chunks: List[DocumentChunk]) -> Iterable[Tuple[DocumentChunk, str, str]]:
        """Keep nearby Markdown headings as context for local, rule-based extraction."""
        for chunk in chunks:
            heading = ""
            for raw_line in chunk.content.split("\n"):
                if re.match(r"^\s*#+\s+", raw_line):
                    heading = self._clean_markdown(raw_line)
                    continue
                cleaned = self._clean_markdown(raw_line)
                if cleaned:
                    yield chunk, cleaned, heading

    def _iter_chunk_lines_with_context(
        self, chunks: List[DocumentChunk]
    ) -> Iterable[Tuple[DocumentChunk, str, str, str]]:
        """Preserve section context across chunk boundaries in long Markdown GDDs."""
        section = ""
        heading = ""
        for chunk in sorted(chunks, key=lambda item: item.chunk_index):
            for raw_line in chunk.content.split("\n"):
                heading_match = re.match(r"^\s*(#+)\s+(.+)$", raw_line)
                if heading_match:
                    level = len(heading_match.group(1))
                    heading = self._clean_markdown(heading_match.group(2))
                    if level <= 2:
                        section = heading
                    continue
                cleaned = self._clean_markdown(raw_line)
                if cleaned:
                    yield chunk, cleaned, section, heading

    def _iter_table_rows(self, chunks: List[DocumentChunk]) -> Iterable[Tuple[DocumentChunk, List[str], List[str]]]:
        """Yield Markdown table rows with their header cells when a supported table is present."""
        for chunk in chunks:
            headers = None
            for raw_line in chunk.content.split("\n"):
                if "|" not in raw_line:
                    headers = None
                    continue
                cells = [self._clean_markdown(cell) for cell in raw_line.strip().strip("|").split("|")]
                if not any(cells) or all(re.fullmatch(r"[-:\s]+", cell or "") for cell in cells):
                    continue
                normalized = [cell.lower() for cell in cells]
                if any(cell in {"name", "npc", "character", "title", "quest"} for cell in normalized):
                    headers = normalized
                    continue
                if headers and len(cells) == len(headers):
                    yield chunk, headers, cells

    def _section(
        self,
        content: Dict[str, Any],
        citations: List[str],
        confidence: str,
        warnings: List[str],
    ) -> Dict[str, Any]:
        return {
            "content": content,
            "citations": citations,
            "confidence": confidence,
            "warnings": warnings,
        }

    def _unique(self, values: Iterable[str]) -> List[str]:
        result = []
        seen = set()
        for value in values:
            normalized = value.strip()
            key = normalized.lower()
            if normalized and key not in seen:
                result.append(normalized)
                seen.add(key)
        return result

    def _objective_to_title(self, objective: str, fallback_index: int) -> str:
        objective = self._clean_markdown(objective)
        objective = re.sub(r"^Objective:\s*", "", objective, flags=re.IGNORECASE)
        objective = re.split(r"\bPlayers\b|\bReward:\b|\.", objective, maxsplit=1, flags=re.IGNORECASE)[0]
        objective = self._clean_title(objective)
        return objective[:80] if objective else f"Quest Hook {fallback_index + 1}"

    def generate_blueprint_from_gdd(
        self,
        db: Session,
        document_id: UUID,
        game_project_id: str,
        supporting_document_ids: List[UUID] | None = None,
    ) -> GameBlueprint:
        document = db.query(Document).filter(
            Document.id == document_id,
            Document.game_project_id == game_project_id,
        ).first()
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Game Design Document not found or not owned by this project.",
            )

        primary_chunks = db.query(DocumentChunk).filter(
            DocumentChunk.document_id == document_id
        ).order_by(DocumentChunk.chunk_index).all()
        if not primary_chunks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Primary document has no text chunks indexed.",
            )

        supporting_ids = []
        for candidate_id in supporting_document_ids or []:
            if candidate_id != document_id and candidate_id not in supporting_ids:
                supporting_ids.append(candidate_id)

        supporting_documents = []
        if supporting_ids:
            supporting_documents = db.query(Document).filter(
                Document.id.in_(supporting_ids),
                Document.game_project_id == game_project_id,
            ).all()
            if len(supporting_documents) != len(supporting_ids):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="One or more supporting sources were not found or are not owned by this project.",
                )
            supporting_by_id = {source.id: source for source in supporting_documents}
            supporting_documents = [supporting_by_id[source_id] for source_id in supporting_ids]

        chunks = primary_chunks + db.query(DocumentChunk).filter(
            DocumentChunk.document_id.in_(supporting_ids)
        ).order_by(DocumentChunk.document_id, DocumentChunk.chunk_index).all()

        summary = self._parse_summary(document.title, chunks)
        narrative = self._parse_narrative(chunks)
        art = self._parse_art_style(chunks)
        npcs = self._parse_npc_archetypes(chunks)
        memory = self._parse_npc_memory(chunks)
        levels = self._parse_level_design(chunks)
        gameplay_systems = self._parse_gameplay_systems(chunks)
        quests = self._parse_quest_hooks(chunks)
        unity_preview = self._generate_unity_preview(
            game_project_id, summary, narrative, art, npcs, memory, levels, gameplay_systems, quests
        )

        blueprint = GameBlueprint(
            title=f"Blueprint: {document.title}",
            document_id=document_id,
            source_document_ids=[str(document_id), *[str(source.id) for source in supporting_documents]],
            game_project_id=game_project_id,
            summary=summary,
            narrative_direction=narrative,
            art_style_direction=art,
            npc_archetypes=npcs,
            npc_memory_design=memory,
            level_design_suggestions=levels,
            gameplay_systems=gameplay_systems,
            quest_hooks=quests,
            unity_runtime_preview=unity_preview,
            status="draft",
        )
        db.add(blueprint)
        db.commit()
        db.refresh(blueprint)
        return blueprint

    def _parse_summary(self, doc_title: str, chunks: List[DocumentChunk]) -> Dict[str, Any]:
        citations: List[str] = []
        description = None
        for chunk, line in self._iter_chunk_lines(chunks):
            if re.search(r"(?:overview|synopsis|game summary|introduction)\s*:", line, re.IGNORECASE):
                description = re.sub(
                    r"^(?:overview|synopsis|game summary|introduction)\s*:\s*",
                    "",
                    line,
                    flags=re.IGNORECASE,
                ).strip()
            elif re.search(r"\b(?:game summary|overview)\b", line, re.IGNORECASE):
                continue
            elif description is None and len(line) > 40 and re.search(r"\b(?:game|player|project)\b", line, re.IGNORECASE):
                description = line
            else:
                continue
            if description:
                citations.append(str(chunk.id))
                break

        warnings = [] if description else ["No explicit game overview found in the source document."]
        return self._section(
            {"title": doc_title, "description": description},
            citations,
            "High" if description else "Low",
            warnings,
        )

    def _parse_narrative(self, chunks: List[DocumentChunk]) -> Dict[str, Any]:
        lines = []
        citations = []
        for chunk, line in self._iter_chunk_lines(chunks):
            if re.search(r"\b(?:lore|story|history|background|narrative|faction)\b", line, re.IGNORECASE) and len(line) > 30:
                lines.append(line)
                citations.append(str(chunk.id))

        lore_background = " ".join(self._unique(lines)[:2]) or None
        warnings = [] if lore_background else ["No detailed narrative or lore section detected in the source document."]
        return self._section(
            {"themes": [], "lore_background": lore_background},
            self._unique(citations),
            "High" if lore_background else "Low",
            warnings,
        )

    def _parse_art_style(self, chunks: List[DocumentChunk]) -> Dict[str, Any]:
        relevant_lines = []
        citations = []
        for chunk, line in self._iter_chunk_lines(chunks):
            if re.search(r"\b(?:art style|visual identity|visual theme|color palette|textures?)\b", line, re.IGNORECASE):
                relevant_lines.append(line)
                citations.append(str(chunk.id))

        visual_theme = None
        for line in relevant_lines:
            match = re.search(
                r"(?:visual identity.*?(?:utilizes|uses)|visual theme\s*:|art style(?: direction)?\s*:)\s*(?:a\s+)?(.+?)(?:\s+theme\b|[.])",
                line,
                re.IGNORECASE,
            )
            if match:
                visual_theme = match.group(1).strip()
                break

        palette_matches = []
        for line in relevant_lines:
            palette_matches.extend(re.findall(
                r"\b(?:warm|elemental|deep|icy|granite|muted|bright|dark)?\s*(?:oranges?|reds?|blues?|gr[ae]ys?|greens?|purples?|yellows?|whites?|blacks?)\b",
                line,
                re.IGNORECASE,
            ))
        color_palette = self._unique(palette_matches)
        visual_notes = self._unique(
            line for line in relevant_lines if re.search(r"\b(?:texture|contrast|environment|character)\b", line, re.IGNORECASE)
        )
        has_source_art = bool(visual_theme or color_palette or visual_notes)
        warnings = [] if has_source_art else ["No art style guidelines or color palette details detected in the source document."]
        return self._section(
            {"visual_theme": visual_theme, "color_palette": color_palette, "visual_notes": visual_notes},
            self._unique(citations),
            "High" if has_source_art else "Low",
            warnings,
        )

    def _parse_npc_archetypes(self, chunks: List[DocumentChunk]) -> Dict[str, Any]:
        found_npcs = []
        citations = []
        seen_names = set()
        for chunk, line in self._iter_chunk_lines(chunks):
            npc_match = re.match(r"^NPC\s+([^:]+):\s*(.+)$", line, re.IGNORECASE)
            if not npc_match:
                continue
            name = self._clean_title(npc_match.group(1))
            description = self._clean_markdown(npc_match.group(2))
            if not name or name.lower() in seen_names:
                continue
            seen_names.add(name.lower())
            found_npcs.append({
                "name": name,
                "archetype": description.split(".")[0].strip() or "Character profile",
                "dialogue_style": description,
            })
            citations.append(str(chunk.id))

        for chunk, headers, cells in self._iter_table_rows(chunks):
            if not any(header in {"name", "npc", "character"} for header in headers):
                continue
            row = dict(zip(headers, cells))
            name = self._clean_title(row.get("name") or row.get("npc") or row.get("character") or "")
            if not name or name.lower() in seen_names:
                continue
            description = row.get("dialogue style") or row.get("dialogue") or row.get("personality") or ""
            archetype = row.get("archetype") or row.get("role") or row.get("type") or "Character profile"
            seen_names.add(name.lower())
            found_npcs.append({
                "name": name,
                "archetype": self._clean_markdown(archetype),
                "dialogue_style": self._clean_markdown(description),
            })
            citations.append(str(chunk.id))

        # Many complete GDDs define characters as subheadings under a cast section,
        # rather than using an "NPC Name:" line or a table. Accept only that explicit
        # structure, so unrelated headings cannot become fabricated runtime NPCs.
        for chunk, line, section, heading in self._iter_chunk_lines_with_context(chunks):
            if not re.search(r"\b(?:main characters|characters|character profiles|npc profiles|npc cast|cast)\b", section, re.IGNORECASE):
                continue
            if heading.lower() == section.lower() or not re.search(r"\b(?:is|are)\b", line, re.IGNORECASE):
                continue
            name = self._clean_title(heading)
            if not name or name.lower() in seen_names:
                continue
            description = self._clean_markdown(line)
            seen_names.add(name.lower())
            found_npcs.append({
                "name": name,
                "archetype": description.split(".")[0].strip() or "Character profile",
                "dialogue_style": description,
            })
            citations.append(str(chunk.id))

        warnings = [] if found_npcs else ["No explicit NPC archetypes or character profiles detected in the source document."]
        return self._section(
            {"npcs": found_npcs[:5]},
            self._unique(citations),
            "High" if found_npcs else "Low",
            warnings,
        )

    def _parse_npc_memory(self, chunks: List[DocumentChunk]) -> Dict[str, Any]:
        subjects = []
        citations = []
        for chunk, line in self._iter_chunk_lines(chunks):
            for subject in re.findall(
                r"\b([A-Z][A-Za-z'-]+(?:\s+[A-Z0-9][A-Za-z0-9'-]+){0,3}\s+(?:Siege|War|Battle|Fall|Rebellion))\b",
                line,
            ):
                subjects.append(subject)
                citations.append(str(chunk.id))

        memory_nodes = [{"subject": subject, "importance": 8} for subject in self._unique(subjects)]
        warnings = [] if memory_nodes else ["No key event memory configurations detected for NPC minds."]
        return self._section(
            {"memory_nodes": memory_nodes},
            self._unique(citations),
            "High" if memory_nodes else "Low",
            warnings,
        )

    def _parse_level_design(self, chunks: List[DocumentChunk]) -> Dict[str, Any]:
        lines = []
        citations = []
        for chunk, line in self._iter_chunk_lines(chunks):
            if re.search(r"\b(?:level design|starting layout|level|map|dungeon|zone|area)\b", line, re.IGNORECASE):
                if len(line) > 30:
                    lines.append(line)
                    citations.append(str(chunk.id))

        level_layout = next(
            (line for line in lines if re.search(r"\b(?:layout|navigate|path|zone)\b", line, re.IGNORECASE)),
            lines[0] if lines else None,
        )
        elements = []
        for line in lines:
            elements.extend(re.findall(
                r"\b(?:[A-Za-z-]+\s+){0,2}(?:vents?|veins?|checkpoints?|gates?|doors?|bridges?|shrines?|terminals?|switches?)\b",
                line,
                re.IGNORECASE,
            ))
        interactive_elements = self._unique(elements)
        has_source_level = bool(level_layout or interactive_elements)
        warnings = [] if has_source_level else ["No level design suggestions or zone outlines found in the source document."]
        return self._section(
            {"level_layout": level_layout, "interactive_elements": interactive_elements},
            self._unique(citations),
            "High" if has_source_level else "Low",
            warnings,
        )

    def _parse_gameplay_systems(self, chunks: List[DocumentChunk]) -> Dict[str, Any]:
        """Extract explicit gameplay and production requirements without inventing them."""
        categories = {
            "technical_constraints": (r"\b(?:technical constraints?|performance|frame ?rate|\bfps\b|memory budget|hardware|target device|engine|network(?:ing)?|offline|save system|resolution)\b", []),
            "accessibility": (r"\b(?:accessibility|subtitles?|captions?|color ?blind|remapp(?:ing|able)|assist mode|difficulty assist|motion sensitiv(?:ity|e))\b", []),
            "platforms_controls": (r"\b(?:platforms?|controls?|input|keyboard|controller|gamepad|touchscreen|mouse)\b", []),
            "core_loop": (r"\b(?:core loop|gameplay loop|gameplay systems?|mechanics?)\b", []),
            "progression": (r"\b(?:progression|level(?:ling|ing)?|experience|xp|upgrade|unlock|skill tree)\b", []),
            "economy": (r"\b(?:economy|currency|gold|credits?|loot|rewards?|shop|crafting|trade)\b", []),
            "design_constraints": (r"\b(?:constraints?|restrictions?|limitations?|must not|cannot|can only|requires?)\b", []),
        }
        citations = []
        for chunk, line, heading in self._iter_chunk_lines_with_heading(chunks):
            context = f"{heading} {line}"
            for name, (pattern, values) in categories.items():
                if not re.search(pattern, context, re.IGNORECASE):
                    continue
                cleaned_line = re.sub(
                    rf"^(?:{pattern})\s*[:\-]\s*",
                    "",
                    line,
                    flags=re.IGNORECASE,
                ).strip()
                if cleaned_line and cleaned_line.lower() != heading.lower():
                    values.append(cleaned_line)
                    citations.append(str(chunk.id))
                break

        content = {name: self._unique(values) for name, (_, values) in categories.items()}
        mvp_scope, scope_citations = self._parse_mvp_scope(chunks)
        if any(mvp_scope.values()):
            content["mvp_scope"] = mvp_scope
            citations.extend(scope_citations)
        found_systems = any(content.values())
        labels = {
            "core_loop": "gameplay loop or mechanics",
            "progression": "progression rules",
            "economy": "economy, rewards, or crafting rules",
            "platforms_controls": "platform or control requirements",
            "accessibility": "accessibility requirements",
            "technical_constraints": "technical or performance constraints",
            "design_constraints": "design constraints",
        }
        warnings = [f"No explicit {label} found in the source document." for name, label in labels.items() if not content[name]]
        return self._section(
            content,
            self._unique(citations),
            "High" if found_systems else "Low",
            warnings,
        )

    def _parse_mvp_scope(self, chunks: List[DocumentChunk]) -> Tuple[Dict[str, List[str]], List[str]]:
        """Read explicit Must/Should/Could headings without assigning our own priorities."""
        scope = {"must_have": [], "should_have": [], "could_have": []}
        citations = []
        heading_to_bucket = {
            "must": "must_have",
            "should": "should_have",
            "could": "could_have",
        }

        for chunk, line, _, heading in self._iter_chunk_lines_with_context(chunks):
            heading_match = re.fullmatch(r"(must|should|could)[-\s]?have", heading, re.IGNORECASE)
            if not heading_match:
                continue
            bucket = heading_to_bucket[heading_match.group(1).lower()]
            item = self._clean_markdown(line)
            normalized_item = item.lower()
            seen_items = [existing.lower() for values in scope.values() for existing in values]
            # Chunk overlap can repeat a Must-have item directly after the
            # Should-have heading, sometimes after the first word was truncated.
            # The first, more complete category is the source of truth.
            is_overlap = any(
                normalized_item == existing
                or (len(normalized_item) >= 12 and normalized_item in existing)
                or (len(existing) >= 12 and existing in normalized_item)
                for existing in seen_items
            )
            if not item or is_overlap:
                continue
            scope[bucket].append(item)
            citations.append(str(chunk.id))

        return {key: self._unique(values) for key, values in scope.items()}, self._unique(citations)

    def _parse_quest_hooks(self, chunks: List[DocumentChunk]) -> Dict[str, Any]:
        found_quests = []
        citations = []
        seen_titles = set()
        seen_objectives = set()
        for chunk, line in self._iter_chunk_lines(chunks):
            quest_match = re.match(r"^(?:Quest Hook\s*(\d+)|Quest\s*(\d+))\s*:\s*(.+)$", line, re.IGNORECASE)
            if not quest_match:
                continue
            quest_body = quest_match.group(3).strip()
            objective_match = re.search(r"Objective:\s*(.*?)(?:\s*Reward:\s*(.*))?$", quest_body, re.IGNORECASE)
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
            found_quests.append({"id": f"q_{len(found_quests)}", "title": title, "objective": objective, "reward": reward})
            citations.append(str(chunk.id))

        for chunk, headers, cells in self._iter_table_rows(chunks):
            if not any(header in {"title", "quest"} for header in headers) or "objective" not in headers:
                continue
            row = dict(zip(headers, cells))
            objective = self._clean_markdown(row.get("objective", ""))
            if not objective:
                continue
            objective_key = re.sub(r"\s+", " ", objective.lower()).strip()
            if objective_key in seen_objectives:
                continue
            seen_objectives.add(objective_key)
            title = self._clean_title(row.get("title") or row.get("quest") or "")
            title = title or self._objective_to_title(objective, len(found_quests))
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
                "reward": self._clean_markdown(row.get("reward", "")),
            })
            citations.append(str(chunk.id))

        # A story-mode level plan is an explicit mission plan. It is safe to turn a
        # labeled level plus its stated focus into a proposed quest without inventing
        # rewards, actors, or objectives that the GDD did not define.
        seen_level_headings = set()
        for chunk, line, section, heading in self._iter_chunk_lines_with_context(chunks):
            if not re.search(r"\b(?:story mode )?(?:level|mission) plan\b", section, re.IGNORECASE):
                continue
            level_match = re.match(r"^(?:Level|Mission)\s*(\d+)?\s*:\s*(.+)$", heading, re.IGNORECASE)
            focus_match = re.match(r"^(?:Focus|Objective)\s*:\s*(.+)$", line, re.IGNORECASE)
            if not level_match or not focus_match:
                continue
            title = self._clean_title(level_match.group(2))
            objective = self._clean_markdown(focus_match.group(1))
            heading_key = heading.lower()
            objective_key = re.sub(r"\s+", " ", objective.lower()).strip()
            if not title or not objective or heading_key in seen_level_headings or objective_key in seen_objectives:
                continue
            seen_level_headings.add(heading_key)
            seen_objectives.add(objective_key)
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
                "reward": "",
            })
            citations.append(str(chunk.id))

        warnings = [] if found_quests else ["No quest chains or reward metrics defined in the source document."]
        return self._section(
            {"quests": found_quests[:5]},
            self._unique(citations),
            "High" if found_quests else "Low",
            warnings,
        )

    def _generate_unity_preview(
        self,
        project_id: str,
        summary: Dict[str, Any],
        narrative: Dict[str, Any],
        art: Dict[str, Any],
        npcs: Dict[str, Any],
        memory: Dict[str, Any],
        levels: Dict[str, Any],
        gameplay_systems: Dict[str, Any],
        quests: Dict[str, Any],
    ) -> Dict[str, Any]:
        return self._section(
            {
                "project_id": project_id,
                "version": "1.0.0",
                "game_summary": summary["content"],
                "narrative": narrative["content"],
                "art_style": art["content"],
                "npcs": npcs["content"].get("npcs", []),
                "npc_memories": memory["content"].get("memory_nodes", []),
                "levels": levels["content"],
                "gameplay_systems": gameplay_systems["content"],
                "quests": quests["content"].get("quests", []),
            },
            [],
            "High",
            [],
        )
