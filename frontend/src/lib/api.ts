const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const activeProjectStorageKey = "gamemind-active-project";
const projectChangeEvent = "gamemind-project-change";

export interface GameProject {
  id: string;
  name: string;
  created_at: string;
}

function activeProjectId() {
  if (typeof window === "undefined") return "default_project";
  return window.localStorage.getItem(activeProjectStorageKey) || "default_project";
}

export function getActiveProjectId() {
  return activeProjectId();
}

export function setActiveProjectId(projectId: string) {
  window.localStorage.setItem(activeProjectStorageKey, projectId);
  window.dispatchEvent(new Event(projectChangeEvent));
}

export function subscribeToProjectChange(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener(projectChangeEvent, callback);

  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener(projectChangeEvent, callback);
  };
}

async function projectFetch(input: RequestInfo | URL, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  if (!headers.has("X-Game-Project-ID")) {
    headers.set("X-Game-Project-ID", activeProjectId());
  }

  return globalThis.fetch(input, { ...init, headers });
}

// API calls are project-scoped unless an individual request supplies its own header.
const fetch = projectFetch;

export interface DocumentResponse {
  id: string;
  title: string;
  content_type: string;
  source_kind: string;
  source_document_id?: string | null;
  revision_number: number;
  created_at: string;
  updated_at: string;
  chunks_count: number;
}

export interface ChunkResponse {
  id: string;
  chunk_index: number;
  content: string;
  metadata?: Record<string, unknown>;
}

export interface DocumentDetailResponse extends DocumentResponse {
  chunks: ChunkResponse[];
}

export interface GddReviewFinding {
  title: string;
  severity: "covered" | "needs_decision" | "conflict";
  message: string;
  guidance?: string | null;
  priority: "critical" | "high" | "medium" | "low";
  recommended_source_kind?: string | null;
  citations: string[];
}

export interface GddReviewResponse {
  document_id: string;
  title: string;
  revision_number: number;
  summary: { covered: number; needs_decision: number; conflicts: number };
  findings: GddReviewFinding[];
}

export interface DesignDecision {
  id: string;
  document_id: string;
  game_project_id: string;
  category: string;
  title: string;
  guidance?: string | null;
  severity: "needs_decision" | "conflict";
  priority: "critical" | "high" | "medium" | "low";
  recommended_source_kind?: string | null;
  evidence_document_id?: string | null;
  decision?: string | null;
  status: "open" | "resolved";
  created_at: string;
  updated_at: string;
}

export interface DecisionCoverageResponse {
  document_id: string;
  revision_number: number;
  summary: {
    source_backed: number;
    needs_source_evidence: number;
    decision_open: number;
    evidence_attached: number;
  };
  items: Array<{
    decision_id: string;
    title: string;
    decision?: string | null;
    status: "open" | "resolved";
    origin_revision_number: number;
    evidence_status: "source_backed" | "needs_source_evidence" | "decision_open" | "evidence_attached";
    evidence_document_id?: string | null;
    evidence_document_title?: string | null;
    citations: string[];
  }>;
}

export interface TechnicalBriefTemplateResponse {
  filename: string;
  content: string;
}

export interface QueryResult {
  chunk_id: string;
  content: string;
  document_id: string;
  title: string;
  chunk_index: number;
  similarity: number;
  confidence: string;
}

export interface QueryResponse {
  query: string;
  results: QueryResult[];
  message?: string | null;
}

export interface HealthResponse {
  status: string;
  database: string;
  chromadb: string;
  ai_mode: string;
  llm_provider: string;
  embedding_provider: string;
  vector_collection: string;
  vector_dimension: number;
}

export const api = {
  async getProjects(): Promise<GameProject[]> {
    const res = await fetch(`${API_BASE_URL}/api/v1/projects/`);
    if (!res.ok) throw new Error("Failed to fetch workspaces");
    return res.json();
  },

  async createProject(name: string): Promise<GameProject> {
    const res = await fetch(`${API_BASE_URL}/api/v1/projects/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Failed to create workspace");
    }
    return res.json();
  },

  async getHealth(): Promise<HealthResponse> {
    const res = await fetch(`${API_BASE_URL}/health`);
    if (!res.ok) throw new Error("Health check failed");
    return res.json();
  },

  async uploadDocument(file: File, sourceKind?: string): Promise<DocumentResponse> {
    const formData = new FormData();
    formData.append("file", file);
    if (sourceKind) formData.append("source_kind", sourceKind);

    const res = await fetch(`${API_BASE_URL}/api/v1/documents/upload`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Failed to upload document");
    }
    return res.json();
  },

  async updateDocumentSourceKind(id: string, sourceKind: string): Promise<DocumentResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/documents/${id}/source-kind`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_kind: sourceKind }),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Could not update source type");
    }
    return res.json();
  },

  async uploadDocumentRevision(documentId: string, file: File): Promise<DocumentResponse> {
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch(`${API_BASE_URL}/api/v1/documents/${documentId}/revision`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Failed to upload document revision");
    }
    return res.json();
  },

  async loadFrostpeakDemoDocument(): Promise<DocumentResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/documents/demo/frostpeak`, {
      method: "POST",
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Failed to load Frostpeak demo document");
    }
    return res.json();
  },

  async getDocuments(): Promise<DocumentResponse[]> {
    const res = await fetch(`${API_BASE_URL}/api/v1/documents`);
    if (!res.ok) throw new Error("Failed to fetch documents");
    return res.json();
  },

  async getDocument(id: string): Promise<DocumentDetailResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/documents/${id}`);
    if (!res.ok) throw new Error("Failed to fetch document details");
    return res.json();
  },

  async reviewDocument(id: string): Promise<GddReviewResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/reviews/documents/${id}`);
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Could not review this source document");
    }
    return res.json();
  },

  async getDesignDecisions(documentId: string): Promise<DesignDecision[]> {
    const res = await fetch(`${API_BASE_URL}/api/v1/decisions?document_id=${documentId}`);
    if (!res.ok) throw new Error("Could not load design decisions");
    return res.json();
  },

  async syncDesignDecisions(documentId: string): Promise<DesignDecision[]> {
    const res = await fetch(`${API_BASE_URL}/api/v1/decisions/sync`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document_id: documentId }),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Could not create design decisions");
    }
    return res.json();
  },

  async getDecisionCoverage(documentId: string): Promise<DecisionCoverageResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/decisions/coverage?document_id=${documentId}`);
    if (!res.ok) throw new Error("Could not assess decision coverage");
    return res.json();
  },

  async updateDesignDecision(id: string, payload: { decision?: string; status?: "open" | "resolved" }): Promise<DesignDecision> {
    const res = await fetch(`${API_BASE_URL}/api/v1/decisions/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Could not save design decision");
    }
    return res.json();
  },

  async attachDecisionEvidence(id: string, evidenceDocumentId: string): Promise<DesignDecision> {
    const res = await fetch(`${API_BASE_URL}/api/v1/decisions/${id}/evidence`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ evidence_document_id: evidenceDocumentId }),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Could not attach the evidence source");
    }
    return res.json();
  },

  async getTechnicalBriefTemplate(documentId: string): Promise<TechnicalBriefTemplateResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/documents/${documentId}/templates/technical-brief`);
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Could not prepare the technical brief template");
    }
    return res.json();
  },

  async deleteDocument(id: string): Promise<void> {
    const res = await fetch(`${API_BASE_URL}/api/v1/documents/${id}`, {
      method: "DELETE",
    });
    if (!res.ok) throw new Error("Failed to delete document");
  },

  async queryLore(query: string, limit: number = 5): Promise<QueryResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/query`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ query, limit }),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Failed to query lore");
    }
    return res.json();
  },

  // NPC Studio CRUD Endpoints
  async getNPCs(): Promise<NPCProfile[]> {
    const res = await fetch(`${API_BASE_URL}/api/v1/npcs`);
    if (!res.ok) throw new Error("Failed to fetch NPC profiles");
    return res.json();
  },

  async getNPC(id: string): Promise<NPCProfile> {
    const res = await fetch(`${API_BASE_URL}/api/v1/npcs/${id}`);
    if (!res.ok) throw new Error("Failed to fetch NPC profile details");
    return res.json();
  },

  async createNPC(npc: NPCProfileCreate): Promise<NPCProfile> {
    const res = await fetch(`${API_BASE_URL}/api/v1/npcs`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(npc),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      if (Array.isArray(errData.detail)) {
        // Validation error array
        const messages = errData.detail.map((d: { loc: (string | number)[]; msg: string }) => `${d.loc.join(".")}: ${d.msg}`);
        throw new Error(messages.join(" | "));
      }
      throw new Error(errData.detail || "Failed to create NPC profile");
    }
    return res.json();
  },

  async updateNPC(id: string, npc: NPCProfileUpdate): Promise<NPCProfile> {
    const res = await fetch(`${API_BASE_URL}/api/v1/npcs/${id}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(npc),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      if (Array.isArray(errData.detail)) {
        const messages = errData.detail.map((d: { loc: (string | number)[]; msg: string }) => `${d.loc.join(".")}: ${d.msg}`);
        throw new Error(messages.join(" | "));
      }
      throw new Error(errData.detail || "Failed to update NPC profile");
    }
    return res.json();
  },

  async deleteNPC(id: string): Promise<void> {
    const res = await fetch(`${API_BASE_URL}/api/v1/npcs/${id}`, {
      method: "DELETE",
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Failed to delete NPC profile");
    }
  },

  async assembleDialogue(payload: DialogueAssembleRequest): Promise<DialogueAssembleResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/dialogue/assemble`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      if (Array.isArray(errData.detail)) {
        const messages = errData.detail.map((d: { loc: (string | number)[]; msg: string }) => `${d.loc.join(".")}: ${d.msg}`);
        throw new Error(messages.join(" | "));
      }
      throw new Error(errData.detail || "Failed to assemble dialogue prompt");
    }
    return res.json();
  },

  async chatDialogue(payload: DialogueChatRequest): Promise<DialogueChatResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/dialogue/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      if (Array.isArray(errData.detail)) {
        const messages = errData.detail.map((d: { loc: (string | number)[]; msg: string }) => `${d.loc.join(".")}: ${d.msg}`);
        throw new Error(messages.join(" | "));
      }
      throw new Error(errData.detail || "Failed to execute dialogue chat");
    }
    return res.json();
  },

  async getOverviewMetrics(): Promise<OverviewMetrics> {
    const res = await fetch(`${API_BASE_URL}/api/v1/analytics/overview`);
    if (!res.ok) throw new Error("Failed to fetch analytics overview");
    return res.json();
  },

  async getNPCCosts(): Promise<NPCCostBreakdown[]> {
    const res = await fetch(`${API_BASE_URL}/api/v1/analytics/costs`);
    if (!res.ok) throw new Error("Failed to fetch NPC cost breakdowns");
    return res.json();
  },

  async getMemoryMetrics(): Promise<MemoryMetrics> {
    const res = await fetch(`${API_BASE_URL}/api/v1/analytics/memory`);
    if (!res.ok) throw new Error("Failed to fetch memory analytics metrics");
    return res.json();
  },

  async getTelemetryLogs(params?: { npc_slug?: string; action_type?: string; limit?: number; offset?: number }): Promise<PaginatedLogs> {
    const queryParts = [];
    if (params?.npc_slug) queryParts.push(`npc_slug=${params.npc_slug}`);
    if (params?.action_type) queryParts.push(`action_type=${params.action_type}`);
    if (params?.limit) queryParts.push(`limit=${params.limit}`);
    if (params?.offset) queryParts.push(`offset=${params.offset}`);
    const queryStr = queryParts.length > 0 ? `?${queryParts.join("&")}` : "";
    const res = await fetch(`${API_BASE_URL}/api/v1/analytics/logs${queryStr}`);
    if (!res.ok) throw new Error("Failed to fetch telemetry logs");
    return res.json();
  },

  async getQuests(): Promise<QuestResponse[]> {
    const res = await fetch(`${API_BASE_URL}/api/v1/quests`);
    if (!res.ok) throw new Error("Failed to fetch quests");
    return res.json();
  },

  async generateHint(payload: HintGenerateRequest): Promise<HintResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/hints/generate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Failed to generate hint");
    }
    return res.json();
  },

  async getHintStatus(questId: string, playerId: string): Promise<HintStatusResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/hints/status?quest_id=${questId}&player_id=${playerId}`);
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Failed to fetch hint status");
    }
    return res.json();
  },

  async generateBlueprint(documentId: string, supportingDocumentIds: string[] = []): Promise<BlueprintResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/blueprints/generate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ document_id: documentId, supporting_document_ids: supportingDocumentIds }),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Failed to generate blueprint");
    }
    return res.json();
  },

  async getBlueprints(): Promise<BlueprintResponse[]> {
    const res = await fetch(`${API_BASE_URL}/api/v1/blueprints`);
    if (!res.ok) throw new Error("Failed to fetch blueprints");
    return res.json();
  },

  async approveBlueprint(blueprintId: string): Promise<BlueprintResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/blueprints/${blueprintId}/approve`, {
      method: "PUT",
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Failed to approve blueprint");
    }
    return res.json();
  },

  async exportBlueprint(blueprintId: string): Promise<BlueprintExportResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/blueprints/${blueprintId}/export`);
    if (!res.ok) throw new Error("Failed to export blueprint");
    return res.json();
  },

  async getBlueprintBrief(blueprintId: string): Promise<{ markdown: string; filename: string }> {
    const res = await fetch(`${API_BASE_URL}/api/v1/blueprints/${blueprintId}/brief`);
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Could not export blueprint brief");
    }
    const disposition = res.headers.get("content-disposition") || "";
    const filename = disposition.match(/filename="?([^";]+)"?/)?.[1] || "gamemind-brief.md";
    return { markdown: await res.text(), filename };
  },

  async getBlueprintReadiness(blueprintId: string): Promise<BlueprintReadinessResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/blueprints/${blueprintId}/readiness`);
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Failed to assess blueprint readiness");
    }
    return res.json();
  },

  async getBlueprintProvenance(blueprintId: string): Promise<BlueprintProvenanceResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/blueprints/${blueprintId}/provenance`);
    if (!res.ok) throw new Error("Could not load blueprint citations");
    return res.json();
  },

  async compareBlueprints(baseBlueprintId: string, revisedBlueprintId: string): Promise<BlueprintComparisonResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/blueprints/${baseBlueprintId}/compare/${revisedBlueprintId}`);
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Failed to compare blueprints");
    }
    return res.json();
  },

  async materializeBlueprint(blueprintId: string, confirmIncomplete: boolean = false): Promise<MaterializationReportResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/blueprints/${blueprintId}/materialize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm_incomplete: confirmIncomplete }),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Failed to materialize blueprint");
    }
    return res.json();
  },

  async getBlueprintRuntimeBundle(blueprintId: string): Promise<BlueprintRuntimeBundleResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/blueprints/${blueprintId}/runtime-bundle`);
    if (!res.ok) throw new Error("Failed to fetch blueprint runtime bundle");
    return res.json();
  },
};

export interface NPCProfile {
  id: string;
  slug: string;
  name: string;
  title?: string;
  personality_summary: string;
  dialogue_style?: string;
  voice_profile?: string;
  faction_alignment?: string;
  animation_hints?: Record<string, string>;
  memory_settings?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface NPCProfileCreate {
  slug: string;
  name: string;
  title?: string;
  personality_summary: string;
  dialogue_style?: string;
  voice_profile?: string;
  faction_alignment?: string;
  animation_hints?: Record<string, string>;
  memory_settings?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export interface NPCProfileUpdate {
  name?: string;
  title?: string;
  personality_summary?: string;
  dialogue_style?: string;
  voice_profile?: string;
  faction_alignment?: string;
  animation_hints?: Record<string, Record<string, string>>;
  memory_settings?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export interface DialogueAssembleRequest {
  npc_slug: string;
  player_message: string;
  selected_chunk_ids?: string[];
}

export interface RetrievedChunkMetadata {
  id: string;
  document_id: string;
  chunk_index: number;
  character_count: number;
}

export interface DialogueAssembleResponse {
  npc_slug: string;
  player_message: string;
  system_prompt: string;
  npc_context: string;
  retrieved_context: string;
  assembled_prompt: string;
  prompt_version: string;
  character_count: number;
  estimated_tokens: number;
  retrieved_chunk_count: number;
  retrieved_chunks: RetrievedChunkMetadata[];
  warnings: string[];
}

export interface DialogueChatRequest extends DialogueAssembleRequest {
  prompt_version?: string;
  model_override?: string;
}

export interface SafetyRating {
  category: string;
  probability: string;
  blocked?: boolean;
}

export interface ChatTelemetry {
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number;
  safety_ratings: SafetyRating[];
  safety_blocked?: boolean;
  error?: string;
}

export interface DialogueChatResponse {
  npc_slug: string;
  response_text: string;
  prompt_version: string;
  model_used: string;
  llm_provider: string;
  telemetry: ChatTelemetry;
  warnings: string[];
}

export interface OverviewMetrics {
  total_cost_usd: number;
  total_requests: number;
  avg_latency_ms: number;
  total_input_tokens: number;
  total_output_tokens: number;
  safety_blocked_count: number;
  error_count: number;
  breakdown_by_action: { action: string; count: number; cost: number }[];
  breakdown_by_model: { model: string; count: number }[];
}

export interface NPCCostBreakdown {
  npc_slug: string;
  requests_count: number;
  total_cost_usd: number;
}

export interface MemoryMetrics {
  active_memories: number;
  archived_memories: number;
  promoted_memories: number;
  average_importance_score: number;
  failed_chroma_indexing_count: number;
}

export interface TelemetryLog {
  id: string;
  conversation_id?: string;
  action_type: string;
  npc_slug: string;
  model_used: string;
  llm_provider: string;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number;
  safety_blocked: boolean;
  safety_ratings?: Record<string, unknown>;
  error?: string;
  created_at: string;
}

export interface PaginatedLogs {
  total: number;
  logs: TelemetryLog[];
}

export interface QuestResponse {
  id: string;
  npc_slug: string;
  title: string;
  description: string;
  difficulty: string;
  gold_reward: number;
  xp_reward: number;
  objectives: unknown[];
}

export interface HintGenerateRequest {
  quest_id: string;
  player_id: string;
  hint_level: number;
}

export interface HintResponse {
  hint_level: number;
  hint: string;
  spoiler_level: string;
  cache_status: "hit" | "miss";
}

export interface HintStatusResponse {
  quest_id: string;
  player_id: string;
  current_level: number;
  last_requested_at: string | null;
  cooldown_remaining_seconds: number;
}

export interface BlueprintSectionResponse {
  content: Record<string, unknown>;
  citations: string[];
  confidence: string;
  warnings: string[];
}

export interface BlueprintResponse {
  id: string;
  game_project_id: string;
  title: string;
  document_id?: string;
  source_document_ids: string[];
  summary: BlueprintSectionResponse;
  narrative_direction: BlueprintSectionResponse;
  art_style_direction: BlueprintSectionResponse;
  npc_archetypes: BlueprintSectionResponse;
  npc_memory_design: BlueprintSectionResponse;
  level_design_suggestions: BlueprintSectionResponse;
  gameplay_systems?: BlueprintSectionResponse;
  quest_hooks: BlueprintSectionResponse;
  unity_runtime_preview: BlueprintSectionResponse;
  status: string;
  materialization_manifest?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface BlueprintReadinessResponse {
  status: "planning_only" | "runtime_review" | "runtime_ready";
  can_materialize: boolean;
  missing_required: string[];
  advisories: string[];
}

export interface BlueprintProvenanceResponse {
  blueprint_id: string;
  sections: Array<{
    section: string;
    citations: Array<{
      chunk_id: string;
      document_id: string;
      document_title: string;
      revision_number: number;
      chunk_index: number;
    }>;
  }>;
}

export interface BlueprintComparisonSection {
  section: string;
  status: string;
  before_warnings: number;
  after_warnings: number;
}

export interface BlueprintComparisonResponse {
  base_blueprint_id: string;
  revised_blueprint_id: string;
  changed_sections: BlueprintComparisonSection[];
}

export interface BlueprintExportResponse {
  api_version: string;
  blueprint_id: string;
  game_project_id: string;
  exported_at: string;
  runtime_data: Record<string, unknown>;
}

export interface MaterializationReportSection {
  created: string[];
  updated: string[];
  skipped: string[];
}

export interface MaterializationReportResponse {
  status: string;
  npcs: MaterializationReportSection;
  quests: MaterializationReportSection;
  memories: MaterializationReportSection;
  flags: MaterializationReportSection;
  warnings: string[];
}

export interface BlueprintRuntimeBundleResponse {
  api_version: string;
  blueprint_id: string;
  game_project_id: string;
  npcs: Record<string, unknown>[];
  quests: Record<string, unknown>[];
  memories: Record<string, unknown>[];
  world_flags: Record<string, unknown>[];
}
