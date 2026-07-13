import pytest
from fastapi.testclient import TestClient
from main import app
from app.database import SessionLocal
from app.models.npc import NPCProfile
from app.models.session import Conversation, Message
import uuid

client = TestClient(app)

@pytest.fixture(scope="module")
def db():
    db_session = SessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()

def test_conversation_persistence_lifecycle(db):
    # Setup: Create a test NPC profile
    npc_slug = f"test_bard_{uuid.uuid4().hex[:6]}"
    npc = NPCProfile(
        slug=npc_slug,
        name="Elidor",
        title="Royal Bard",
        personality_summary="A cheerful bard who tells stories and plays the lute.",
        dialogue_style="Polite, uses musical metaphors.",
        faction_alignment="bard_guild"
    )
    db.add(npc)
    db.commit()
    db.refresh(npc)

    # 1. Test Conversation Creation
    create_payload = {"npc_slug": npc_slug}
    response = client.post("/api/v1/conversations", json=create_payload)
    assert response.status_code == 201
    conv_data = response.json()
    assert "id" in conv_data
    assert conv_data["npc_slug"] == npc_slug
    assert conv_data["title"] == "Conversation with Elidor"
    assert conv_data["status"] == "active"
    conv_id = conv_data["id"]

    # Verify conversations lists
    list_response = client.get("/api/v1/conversations")
    assert list_response.status_code == 200
    assert any(c["id"] == conv_id for c in list_response.json())

    # Filter list by slug
    list_filtered = client.get(f"/api/v1/conversations?npc_slug={npc_slug}")
    assert list_filtered.status_code == 200
    assert len(list_filtered.json()) == 1

    # 2. Test Message Persistence
    chat_payload = {
        "npc_slug": npc_slug,
        "player_message": "Play me a tune, bard.",
        "conversation_id": conv_id,
        "selected_chunk_ids": []
    }
    
    # We patch settings to ensure LLM_PROVIDER = mock
    from unittest.mock import patch
    with patch("app.api.v1.dialogue.settings") as mock_settings:
        mock_settings.LLM_PROVIDER = "mock"
        mock_settings.LOCAL_MODEL_NAME = "mock-model"
        
        chat_response = client.post("/api/v1/dialogue/chat", json=chat_payload)
        assert chat_response.status_code == 200
        chat_data = chat_response.json()
        assert chat_data["conversation_id"] == conv_id
        assert "response_text" in chat_data

        # Verify messages written to database
        db_messages = db.query(Message).filter(Message.conversation_id == conv_id).all()
        assert len(db_messages) == 2
        assert db_messages[0].sender == "player"
        assert db_messages[0].content == "Play me a tune, bard."
        assert db_messages[1].sender == "npc"
        assert db_messages[1].content.startswith("Elidor:")
        assert "do not have enough grounded lore" in db_messages[1].content
        npc_response_text = db_messages[1].content

    # 3. Test Session Restoration
    # Fetch details endpoint
    detail_response = client.get(f"/api/v1/conversations/{conv_id}")
    assert detail_response.status_code == 200
    detail_data = detail_response.json()
    assert len(detail_data["messages"]) == 2
    assert detail_data["messages"][0]["sender"] == "player"
    assert detail_data["messages"][1]["sender"] == "npc"

    # Send a second turn to test dialogue history injection in prompts
    second_chat_payload = {
        "npc_slug": npc_slug,
        "player_message": "What is the name of your lute?",
        "conversation_id": conv_id,
        "selected_chunk_ids": []
    }
    with patch("app.api.v1.dialogue.settings") as mock_settings:
        mock_settings.LLM_PROVIDER = "mock"
        mock_settings.LOCAL_MODEL_NAME = "mock-model"
        
        second_response = client.post("/api/v1/dialogue/chat", json=second_chat_payload)
        assert second_response.status_code == 200
        
        # Verify db now has 4 messages
        db_messages_after = db.query(Message).filter(Message.conversation_id == conv_id).order_by(Message.created_at).all()
        assert len(db_messages_after) == 4
        assert db_messages_after[2].sender == "player"
        assert db_messages_after[2].content == "What is the name of your lute?"
        assert db_messages_after[3].sender == "npc"
        
        # Check that the prompt assembly is using the history
        from app.services.dialogue_service import DialogueService
        from app.schemas import DialogueAssembleRequest
        assemble_req = DialogueAssembleRequest(npc_slug=npc_slug, player_message="Third message.", selected_chunk_ids=[])
        # Retrieve the first two messages to pass as history
        history_msgs = db_messages_after[:2]
        assembled_data = DialogueService.assemble_prompt(db, assemble_req, history=history_msgs)
        # Check that historical dialogue session transcript is built in
        assert "Player: Play me a tune, bard." in assembled_data.assembled_prompt
        assert npc_response_text in assembled_data.assembled_prompt

    # 4. Test Deleted Conversation Handling
    delete_response = client.delete(f"/api/v1/conversations/{conv_id}")
    assert delete_response.status_code == 204

    # Verify conversation GET returns 404
    get_deleted = client.get(f"/api/v1/conversations/{conv_id}")
    assert get_deleted.status_code == 404

    # Verify associated messages are cascade-deleted in DB
    db_messages_deleted = db.query(Message).filter(Message.conversation_id == conv_id).all()
    assert db_messages_deleted == []

    # Verify chat route fails if passing deleted conversation ID
    failed_chat_payload = {
        "npc_slug": npc_slug,
        "player_message": "Hello?",
        "conversation_id": conv_id,
        "selected_chunk_ids": []
    }
    chat_deleted = client.post("/api/v1/dialogue/chat", json=failed_chat_payload)
    assert chat_deleted.status_code == 404

    # 5. Test NPC Soft-Delete Compatibility
    # Soft delete the NPC Elidor
    client.delete(f"/api/v1/npcs/{npc.id}")
    
    # Try to create new conversation for deleted NPC
    failed_create = client.post("/api/v1/conversations", json={"npc_slug": npc_slug})
    assert failed_create.status_code == 404
    assert "not found or has been deleted" in failed_create.json()["detail"]
