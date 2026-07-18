"""merge auth and decision migration heads

Revision ID: d8f1c3a5e762
Revises: b2c3d4e5f6a7, c7e4f9a2b651
Create Date: 2026-07-17 10:20:00.000000
"""
from typing import Sequence, Union


revision: str = "d8f1c3a5e762"
down_revision: Union[str, Sequence[str], None] = ("b2c3d4e5f6a7", "c7e4f9a2b651")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
