# Runtime API Integration

Use this workflow when a game client wants to consume GameMind data at runtime.

GameMind should be treated as a backend intelligence layer. The game engine remains responsible for rendering, input, animation, save files, combat, inventory, and scene logic.

## Architecture

```text
Dashboard Workspace
  -> approve blueprint
  -> materialize runtime records

Runtime API
  -> runtime bundle
  -> dialogue
  -> quest progress
  -> progressive hints
  -> world flags

Game Client
  -> Unity, Godot, Unreal, web, or custom REST client
```

## Integration Rules

- Keep GameMind logic server-side.
- Keep engine-specific presentation client-side.
- Do not hardcode generated lore into scenes.
- Fetch runtime data from stable REST contracts.
- Treat animation suggestions as hints, not commands.
- Always support fallback UI when the backend is unavailable.

## Required Headers

Most runtime calls should include:

```http
X-Game-Project-ID: default_project
X-Player-ID: default_player
Content-Type: application/json
```

Use real project/player IDs in a production game.

## Core Endpoints

### Health

```http
GET /health
```

Use this before showing runtime controls.

### Latest Runtime Bundle

```http
GET /api/v1/blueprints/runtime/latest-bundle
```

Returns the newest materialized blueprint data for the active project.

The bundle can include:

- NPC profiles.
- Quests.
- NPC memories.
- World flags.

### Dialogue

```http
POST /api/v1/dialogue/chat
```

Example body:

```json
{
  "npc_slug": "eldrin",
  "player_message": "Who is King Arven?"
}
```

Only send `conversation_id` when you already have a valid UUID from a previous conversation.

### Quest Progress

```http
POST /api/v1/quests/progress
```

Example body:

```json
{
  "quest_id": "854c6755-aae8-4ace-92cc-723c48af4971",
  "player_id": "default_player"
}
```

### Progressive Hint

```http
POST /api/v1/hints/generate
```

Example body:

```json
{
  "quest_id": "854c6755-aae8-4ace-92cc-723c48af4971",
  "player_id": "default_player",
  "hint_level": 1
}
```

## Client Responsibilities

The client should map runtime responses into game presentation:

- Dialogue text -> dialogue box.
- `suggested_animation` -> local animation allowlist.
- NPC emotions -> expression, voice tone, or UI state.
- Quest data -> quest journal.
- Hint data -> hint panel.
- World flags -> local state checks.

## Error Handling

Handle these cases gracefully:

- Backend not running.
- No materialized blueprint.
- Quest already accepted.
- Invalid project/player ID.
- Invalid conversation UUID.
- Empty or weak source data.

Do not turn a single dialogue or quest error into a full-scene failure. Keep runtime action errors local to the relevant UI.

## Current Unity Adapter

The Unity folder contains a proof-of-integration adapter:

```text
Unity/Assets/Scripts/GameMindApiClient.cs
Unity/Assets/Scripts/GameMindUiController.cs
Unity/Assets/Scripts/NpcInteractionController.cs
Unity/Assets/Scripts/Contracts/DialogueDTO.cs
```

Use it as a reference implementation, not as a required scene architecture.

