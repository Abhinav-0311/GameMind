import uuid
from datetime import datetime
from typing import List, Optional, Tuple, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from app.models.graph import WorldEntity, WorldEntityVersion, WorldRelationship
from app.services.graph_cache import graph_cache

class GraphRepository:
    def __init__(self, db: Optional[Session] = None):
        self.db = db

    def _lock_entities_ordered(self, slugs: List[str], db: Optional[Session] = None, game_project_id: str = "default_project") -> List[WorldEntity]:
        """Locks entity records in alphabetical order of slugs to prevent deadlocks, scoped by project."""
        session = db or self.db
        if not session:
            raise ValueError("Database session is required for locking.")
        sorted_slugs = sorted(list(set(slugs)))
        return session.query(WorldEntity).filter(
            WorldEntity.slug.in_(sorted_slugs),
            WorldEntity.game_project_id == game_project_id
        ).order_by(WorldEntity.slug).with_for_update().all()

    def get_active_entity_by_slug(self, slug_or_db: Any, slug: Optional[str] = None, db: Optional[Session] = None, game_project_id: str = "default_project") -> Tuple[Optional[WorldEntity], Optional[WorldEntityVersion]]:
        """Fetch the active entity and its current active version (valid_to is null) scoped by project."""
        if isinstance(slug_or_db, str):
            target_slug = slug_or_db
            session = db or self.db
        else:
            session = slug_or_db
            target_slug = slug

        if not session:
            raise ValueError("Database session is required.")

        entity = self.get_entity_by_slug(session, target_slug, game_project_id=game_project_id)
        if not entity:
            return None, None
        active_ver = self.get_active_entity_version(session, entity.id)
        return entity, active_ver

    def get_active_relationship(
        self,
        db: Session,
        source_slug: str,
        target_slug: str,
        rel_type: str,
        game_project_id: str = "default_project",
        for_update: bool = False,
    ) -> Optional[WorldRelationship]:
        """Fetch the active relationship edge between source and target slugs scoped by project."""
        source = self.get_entity_by_slug(db, source_slug, game_project_id=game_project_id)
        target = self.get_entity_by_slug(db, target_slug, game_project_id=game_project_id)
        if not source or not target:
            return None
        query = db.query(WorldRelationship).filter(
            WorldRelationship.source_id == source.id,
            WorldRelationship.target_id == target.id,
            WorldRelationship.rel_type == rel_type,
            WorldRelationship.valid_to.is_(None)
        )
        if for_update:
            query = query.with_for_update()
        return query.first()

    def get_entity_by_slug(self, db: Session, slug: str, game_project_id: str = "default_project") -> Optional[WorldEntity]:
        """Fetch a WorldEntity by slug scoped by project."""
        return db.query(WorldEntity).filter(
            WorldEntity.slug == slug,
            WorldEntity.game_project_id == game_project_id
        ).first()

    def get_active_entity_version(
        self, db: Session, entity_id: uuid.UUID, as_of: Optional[datetime] = None
    ) -> Optional[WorldEntityVersion]:
        """Fetch the active entity version at a specific timestamp (or current if as_of is None)."""
        query = db.query(WorldEntityVersion).filter(WorldEntityVersion.entity_id == entity_id)
        if as_of:
            query = query.filter(
                and_(
                    WorldEntityVersion.valid_from <= as_of,
                    or_(
                        WorldEntityVersion.valid_to.is_(None),
                        WorldEntityVersion.valid_to > as_of
                    )
                )
            )
        else:
            query = query.filter(WorldEntityVersion.valid_to.is_(None))
        return query.first()

    def get_adjacent_relationships(
        self, db: Session, entity_id: uuid.UUID, direction: str = "both", as_of: Optional[datetime] = None
    ) -> List[WorldRelationship]:
        """
        Query adjacent relationship edges. Does not perform row-level locking.
        Filters out soft-deleted records based on the as_of timestamp.
        """
        query = db.query(WorldRelationship)
        
        # Apply direction filter
        if direction == "out":
            query = query.filter(WorldRelationship.source_id == entity_id)
        elif direction == "in":
            query = query.filter(WorldRelationship.target_id == entity_id)
        elif direction == "both":
            query = query.filter(
                or_(
                    WorldRelationship.source_id == entity_id,
                    WorldRelationship.target_id == entity_id
                )
            )
        else:
            raise ValueError(f"Invalid direction: {direction}. Must be 'both', 'in', or 'out'.")

        # Apply temporal filtering (as_of)
        if as_of:
            query = query.filter(
                and_(
                    WorldRelationship.valid_from <= as_of,
                    or_(
                        WorldRelationship.valid_to.is_(None),
                        WorldRelationship.valid_to > as_of
                    )
                )
            )
        else:
            query = query.filter(WorldRelationship.valid_to.is_(None))

        return query.all()

    # Mutation Helpers (which will increment stamps)
    def create_entity(
        self,
        db: Optional[Session] = None,
        slug: Optional[str] = None,
        entity_type: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        importance_score: int = 0,
        properties: Optional[dict] = None,
        game_project_id: str = "default_project"
    ) -> WorldEntity:
        """Create a WorldEntity and its initial version, and increment its version stamp, scoped by project."""
        session = db or self.db
        if not session:
            raise ValueError("Database session is required.")
        entity = WorldEntity(slug=slug, entity_type=entity_type, game_project_id=game_project_id)
        session.add(entity)
        session.flush()  # populate entity.id

        version = WorldEntityVersion(
            entity_id=entity.id,
            version=1,
            name=name,
            description=description,
            importance_score=importance_score,
            properties=properties or {}
        )
        session.add(version)
        session.commit()
        session.refresh(entity)

        # Increment stamp
        graph_cache.increment_entity_stamp(slug)
        return entity

    def update_entity(
        self,
        db: Optional[Session] = None,
        slug: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        importance_score: Optional[int] = None,
        properties: Optional[dict] = None,
        game_project_id: str = "default_project"
    ) -> Optional[WorldEntityVersion]:
        """Update an entity by adding a new temporal version and incrementing its version stamp, scoped by project."""
        session = db or self.db
        if not session:
            raise ValueError("Database session is required.")
        entity = self.get_entity_by_slug(session, slug, game_project_id=game_project_id)
        if not entity:
            return None

        # Fetch current active version
        active_ver = self.get_active_entity_version(session, entity.id)
        if not active_ver:
            return None

        now = datetime.utcnow()
        # Retire old active version
        active_ver.valid_to = now

        # Create new version
        new_ver = WorldEntityVersion(
            entity_id=entity.id,
            version=active_ver.version + 1,
            name=name if name is not None else active_ver.name,
            description=description if description is not None else active_ver.description,
            importance_score=importance_score if importance_score is not None else active_ver.importance_score,
            properties=properties if properties is not None else active_ver.properties,
            valid_from=now
        )
        session.add(new_ver)
        session.commit()
        session.refresh(new_ver)

        # Increment stamp
        graph_cache.increment_entity_stamp(slug)
        return new_ver

    def delete_entity(self, db: Optional[Session] = None, slug: Optional[str] = None, game_project_id: str = "default_project") -> bool:
        """Soft delete an entity by retiring its active version, and increment its version stamp, scoped by project."""
        session = db or self.db
        if not session:
            raise ValueError("Database session is required.")
        entity = self.get_entity_by_slug(session, slug, game_project_id=game_project_id)
        if not entity:
            return False

        active_ver = self.get_active_entity_version(session, entity.id)
        if not active_ver:
            return False

        active_ver.valid_to = datetime.utcnow()
        session.commit()

        # Increment stamp
        graph_cache.increment_entity_stamp(slug)
        return True

    def create_relationship(
        self,
        db: Optional[Session] = None,
        source_slug: Optional[str] = None,
        target_slug: Optional[str] = None,
        rel_type: Optional[str] = None,
        weight: float = 1.0,
        properties: Optional[dict] = None,
        game_project_id: str = "default_project"
    ) -> Optional[WorldRelationship]:
        """Create a relationship edge between two entities and increment its version stamp, scoped by project."""
        session = db or self.db
        if not session:
            raise ValueError("Database session is required.")
        source = self.get_entity_by_slug(session, source_slug, game_project_id=game_project_id)
        target = self.get_entity_by_slug(session, target_slug, game_project_id=game_project_id)
        if not source or not target:
            return None

        rel = WorldRelationship(
            source_id=source.id,
            target_id=target.id,
            rel_type=rel_type,
            weight=weight,
            version=1,
            properties=properties or {}
        )
        session.add(rel)
        session.commit()
        session.refresh(rel)

        # Increment stamp
        graph_cache.increment_relationship_stamp(source_slug, target_slug, rel_type)
        return rel

    def update_relationship(
        self,
        db: Optional[Session] = None,
        source_slug: Optional[str] = None,
        target_slug: Optional[str] = None,
        rel_type: Optional[str] = None,
        weight: Optional[float] = None,
        properties: Optional[dict] = None,
        game_project_id: str = "default_project"
    ) -> Optional[WorldRelationship]:
        """Update a relationship by retiring the old active one and creating a new version, scoped by project."""
        session = db or self.db
        if not session:
            raise ValueError("Database session is required.")
        source = self.get_entity_by_slug(session, source_slug, game_project_id=game_project_id)
        target = self.get_entity_by_slug(session, target_slug, game_project_id=game_project_id)
        if not source or not target:
            return None

        # Fetch current active relationship
        active_rel = session.query(WorldRelationship).filter(
            WorldRelationship.source_id == source.id,
            WorldRelationship.target_id == target.id,
            WorldRelationship.rel_type == rel_type,
            WorldRelationship.valid_to.is_(None)
        ).with_for_update().first()

        if not active_rel:
            return None

        now = datetime.utcnow()
        active_rel.valid_to = now

        new_rel = WorldRelationship(
            source_id=source.id,
            target_id=target.id,
            rel_type=rel_type,
            weight=weight if weight is not None else active_rel.weight,
            version=active_rel.version + 1,
            properties=properties if properties is not None else active_rel.properties,
            valid_from=now
        )
        session.add(new_rel)
        session.commit()
        session.refresh(new_rel)

        # Increment stamp
        graph_cache.increment_relationship_stamp(source_slug, target_slug, rel_type)
        return new_rel

    def delete_relationship(
        self, 
        db: Optional[Session] = None, 
        source_slug: Optional[str] = None, 
        target_slug: Optional[str] = None, 
        rel_type: Optional[str] = None,
        game_project_id: str = "default_project"
    ) -> bool:
        """Soft delete a relationship edge by setting valid_to and increment its version stamp, scoped by project."""
        session = db or self.db
        if not session:
            raise ValueError("Database session is required.")
        source = self.get_entity_by_slug(session, source_slug, game_project_id=game_project_id)
        target = self.get_entity_by_slug(session, target_slug, game_project_id=game_project_id)
        if not source or not target:
            return False

        active_rel = session.query(WorldRelationship).filter(
            WorldRelationship.source_id == source.id,
            WorldRelationship.target_id == target.id,
            WorldRelationship.rel_type == rel_type,
            WorldRelationship.valid_to.is_(None)
        ).first()

        if not active_rel:
            return False

        active_rel.valid_to = datetime.utcnow()
        session.commit()

        # Increment stamp
        graph_cache.increment_relationship_stamp(source_slug, target_slug, rel_type)
        return True

graph_repo = GraphRepository()
