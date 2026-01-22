"""
Base declarative class for SQLAlchemy models.

All models should inherit from this Base.
"""
from sqlalchemy.orm import declarative_base

# Single Base instance for all models
Base = declarative_base()
