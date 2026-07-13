# Unity Integration Notes

The Unity project is a reference adapter for GameMind runtime APIs. It proves that a Unity scene can consume runtime bundles, NPC dialogue, quests, and progressive hints from the backend.

It is not intended to be a universal Unity framework. Every game will have its own input system, UI framework, animation controllers, save system, and scene architecture.

## What To Reuse

Reuse these ideas:

- DTO classes for parsing runtime responses.
- `GameMindApiClient` request structure.
- Runtime bundle loading.
- Local error handling.
- Animation allowlist mapping.

Do not blindly reuse the demo UI if your game already has a UI system.

## Setup

1. Start the backend:

```bash
docker compose up -d --build
```

2. Confirm health:

```text
http://localhost:8000/health
```

3. In the dashboard:

- Load the Frostpeak demo source.
- Generate a blueprint.
- Approve it.
- Materialize it.

4. Open Unity:

```text
Unity/Assets/Scenes/GameMindVerticalSlice.unity
```

5. Press Play.

Expected:

- Status shows runtime ready.
- Quest panel appears.
- Talk button sends a dialogue request.
- Accept quest unlocks hints.
- Hint button cycles progressive hints.

## Important Client Detail

For a new dialogue, do not send an empty `conversation_id`.

Correct:

```json
{
  "npc_slug": "eldrin",
  "player_message": "Who is King Arven?"
}
```

Only send `conversation_id` when it is a valid UUID.

## Animation Mapping

The backend can return a `suggested_animation`, but Unity should never blindly trust it.

Recommended client behavior:

```text
backend suggested animation -> local allowlist -> animator trigger
```

If no Animator Controller is assigned, skip animation quietly.

## What To Customize

Real games should replace:

- Demo UI panels.
- Demo keyboard shortcuts.
- Procedural placeholder scene dressing.
- Hardcoded sample question.
- Default player/project IDs.

Keep the API client contract and adapt presentation to your game.

