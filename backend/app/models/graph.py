import uuid
from sqlalchemy import Column, String, Integer, Float, Text, ForeignKey, ForeignKeyConstraint, DateTime, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base, ProjectScopedMixin

class WorldEntity(Base, ProjectScopedMixin):
    __tablename__ = "world_entities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(String(100), nullable=False)
    entity_type = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Constraints
    __table_args__ = (
        UniqueConstraint("game_project_id", "slug", name="uq_entity_project_slug"),
        UniqueConstraint("game_project_id", "id", name="uq_entity_project_id"),
    )

    # Relationships
    versions = relationship(
        "WorldEntityVersion",
        back_populates="entity",
        cascade="all, delete-orphan",
        lazy="select"
    )
    relationships_out = relationship(
        "WorldRelationship",
        foreign_keys="[WorldRelationship.source_id]",
        back_populates="source",
        cascade="all, delete-orphan"
    )
    relationships_in = relationship(
        "WorldRelationship",
        foreign_keys="[WorldRelationship.target_id]",
        back_populates="target",
        cascade="all, delete-orphan"
    )


class WorldEntityVersion(Base):
    __tablename__ = "world_entity_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id = Column(UUID(as_uuid=True), ForeignKey("world_entities.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    importance_score = Column(Integer, nullable=False, default=0)
    properties = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    valid_from = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    valid_to = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    entity = relationship("WorldEntity", back_populates="versions")

    # Constraints & Indexes
    __table_args__ = (
        UniqueConstraint("entity_id", "version", name="uq_entity_version"),
        # Partial Unique Index to enforce active-version constraints
        Index(
            "uq_active_entity_version",
            "entity_id",
            unique=True,
            postgresql_where=text("valid_to IS NULL")
        ),
        # Indexes for Temporal Query Optimization
        Index(
            "ix_entities_temporal",
            "entity_id",
            "valid_from",
            "valid_to"
        ),
        # Recommended Active Indexes (Amendment 5)
        Index(
            "ix_active_entity_versions",
            "entity_id",
            postgresql_where=text("valid_to IS NULL")
        )
    )


class WorldRelationship(Base, ProjectScopedMixin):
    __tablename__ = "world_relationships"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), nullable=False)
    target_id = Column(UUID(as_uuid=True), nullable=False)
    rel_type = Column(String(50), nullable=False)
    weight = Column(Float, nullable=False, default=1.0)
    version = Column(Integer, nullable=False, default=1)
    valid_from = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    valid_to = Column(DateTime(timezone=True), nullable=True)
    properties = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))

    # Relationships
    source = relationship("WorldEntity", foreign_keys=[source_id], back_populates="relationships_out")
    target = relationship("WorldEntity", foreign_keys=[target_id], back_populates="relationships_in")

    # Constraints & Indexes
    __table_args__ = (
        ForeignKeyConstraint(
            ["game_project_id", "source_id"],
            ["world_entities.game_project_id", "world_entities.id"],
            ondelete="CASCADE",
            name="fk_world_relationships_source"
        ),
        ForeignKeyConstraint(
            ["game_project_id", "target_id"],
            ["world_entities.game_project_id", "world_entities.id"],
            ondelete="CASCADE",
            name="fk_world_relationships_target"
        ),
        UniqueConstraint("source_id", "target_id", "rel_type", "version", name="uq_relationship_version"),
        # Partial Unique Index to enforce active relationship constraints
        Index(
            "uq_active_relationship",
            "source_id",
            "target_id",
            "rel_type",
            unique=True,
            postgresql_where=text("valid_to IS NULL")
        ),
        # Indexes for Temporal Query Optimization
        Index(
            "ix_relationships_temporal",
            "source_id",
            "target_id",
            "valid_from",
            "valid_to"
        ),
        # Recommended Active Indexes (Amendment 5)
        Index(
            "ix_active_relationship_source",
            "source_id",
            postgresql_where=text("valid_to IS NULL")
        ),
        Index(
            "ix_active_relationship_target",
            "target_id",
            postgresql_where=text("valid_to IS NULL")
        )
    )


class RelationshipTypeRule(Base):
    __tablename__ = "relationship_type_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rel_type = Column(String(50), nullable=False)
    allowed_source_type = Column(String(50), nullable=False)
    allowed_target_type = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Constraints
    __table_args__ = (
        UniqueConstraint("rel_type", "allowed_source_type", "allowed_target_type", name="uq_taxonomy_rule"),
    )


class PendingIngest(Base):
    __tablename__ = "pending_ingests"

    validation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payload = Column(JSONB, nullable=False)
    reason_blocked = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now() + interval '1 hour'")
    )


class ConsistencyOverride(Base):
    __tablename__ = "consistency_overrides"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    validation_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True
    )
    blocked_payload = Column(JSONB, nullable=True)
    reason_blocked = Column(Text, nullable=True)
    override_applied_by = Column(String(100), nullable=False)
    override_reason = Column(Text, nullable=False)
    override_timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

