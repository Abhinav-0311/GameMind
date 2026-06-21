from fastapi import Header

def get_game_project_id(x_game_project_id: str = Header(default="default_project", alias="X-Game-Project-ID")) -> str:
    return x_game_project_id

def get_player_id(x_player_id: str = Header(default="default_player", alias="X-Player-ID")) -> str:
    return x_player_id
