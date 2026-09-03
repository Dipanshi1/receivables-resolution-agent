"""Base declarative model for domain entities.

Defines the SQLAlchemy DeclarativeBase and centralized MetaData with
standard PostgreSQL naming conventions for indexes and constraints.
Domain tables are not defined here and will be implemented in later phases.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# PostgreSQL naming conventions for constraints and indexes
POSTGRES_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=POSTGRES_NAMING_CONVENTION)


class Base(DeclarativeBase):
    """Base class for all domain models."""

    metadata = metadata
