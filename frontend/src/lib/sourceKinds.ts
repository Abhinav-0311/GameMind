export const sourceKinds = ["gdd", "lore", "npc_sheet", "quest_brief", "level_brief", "technical_brief", "general"] as const;

export type SourceKind = (typeof sourceKinds)[number];

export const sourceKindMeta: Record<SourceKind, { label: string; impact: string[]; description: string }> = {
  gdd: {
    label: "Game design document",
    impact: ["Game summary", "Gameplay systems", "Levels", "Quests"],
    description: "Best for a complete first blueprint and production constraints.",
  },
  lore: {
    label: "Lore and world building",
    impact: ["Narrative", "NPCs", "Memory"],
    description: "Strengthens world consistency, factions, characters, and grounded dialogue.",
  },
  npc_sheet: {
    label: "NPC and character sheet",
    impact: ["NPCs", "Memory", "Narrative"],
    description: "Strengthens character roles, dialogue context, and memory design.",
  },
  quest_brief: {
    label: "Quest brief",
    impact: ["Quests", "Levels", "Gameplay systems"],
    description: "Strengthens objectives, rewards, gates, and progressive hints.",
  },
  level_brief: {
    label: "Level brief",
    impact: ["Levels", "Gameplay systems", "Art style"],
    description: "Strengthens spaces, interactions, progression gates, and environmental direction.",
  },
  technical_brief: {
    label: "Technical brief",
    impact: ["Gameplay systems", "Runtime"],
    description: "Strengthens platform, control, performance, and runtime constraints.",
  },
  general: {
    label: "General game notes",
    impact: ["Game summary", "Narrative"],
    description: "Useful supporting material. Assign a more specific type when its role is clear.",
  },
};

export function asSourceKind(value: string): SourceKind {
  return sourceKinds.includes(value as SourceKind) ? (value as SourceKind) : "general";
}
