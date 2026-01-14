"""Database connection and session management."""

import os
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import String, Text, Integer, Date, Boolean, JSON

from app.config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""
    pass


# Database engine (initialized lazily)
_engine = None
_async_session_maker = None


def _is_db_configured() -> bool:
    """Check if a real database is configured."""
    settings = get_settings()
    db_url = settings.database_url
    # Skip if using default placeholder or SQLite in-memory
    if not db_url or "localhost" in db_url:
        # Check if PostgreSQL is likely available
        return False
    return True


async def init_db():
    """Initialize database tables if database is configured."""
    global _engine, _async_session_maker
    
    settings = get_settings()
    
    # Check if we should use a database
    db_url = settings.database_url
    
    # Try to use SQLite for local development if PostgreSQL isn't available
    if "postgresql" in db_url:
        # Try PostgreSQL, fall back to SQLite if it fails
        try:
            _engine = create_async_engine(
                db_url,
                echo=False,
                pool_pre_ping=True,
            )
            # Test connection
            async with _engine.begin() as conn:
                from app.db import models  # noqa: F401
                await conn.run_sync(Base.metadata.create_all)
            
            _async_session_maker = async_sessionmaker(
                _engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            print("✓ Connected to PostgreSQL database")
            # Run migrations for PostgreSQL
            await run_migrations()
            return
        except Exception as e:
            print(f"⚠ PostgreSQL not available ({e}), using in-memory mode")
            _engine = None
            _async_session_maker = None
    
    # Fallback: Use SQLite for development
    try:
        sqlite_url = "sqlite+aiosqlite:///./papers.db"
        _engine = create_async_engine(sqlite_url, echo=False)
        
        async with _engine.begin() as conn:
            from app.db import models  # noqa: F401
            await conn.run_sync(Base.metadata.create_all)
        
        _async_session_maker = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        print("✓ Using SQLite database (papers.db)")
        # Run migrations for SQLite
        await run_migrations()
    except Exception as e:
        print(f"⚠ Database initialization failed ({e}), using in-memory cache only")
        _engine = None
        _async_session_maker = None


async def run_migrations():
    """
    Run database migrations to add missing columns.
    
    This function checks the database schema and adds any missing columns
    based on the SQLAlchemy model definition. It handles both SQLite and PostgreSQL.
    """
    if not is_db_available() or _engine is None:
        return
    
    try:
        from sqlalchemy import text
        
        async with _engine.begin() as conn:
            # Check database type
            db_type = str(_engine.url).split("://")[0]
            is_sqlite = "sqlite" in db_type
            
            # Get existing columns from database
            if is_sqlite:
                result = await conn.execute(text("PRAGMA table_info(paper)"))
                existing_columns = {row[1] for row in result.fetchall()}
            else:
                # PostgreSQL
                result = await conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'paper'
                """))
                existing_columns = {row[0] for row in result.fetchall()}
            
            migrations_applied = []
            
            # Complete list of all columns that should exist in the Paper model
            # This list is based on backend/app/db/models.py Paper class definition
            required_columns = [
                ("publication_date", "DATE"),
                ("urls_json", "JSONB" if not is_sqlite else "JSON"),
                ("keywords_json", "JSONB" if not is_sqlite else "JSON"),
                ("comments", "TEXT"),
                ("number_of_pages", "INTEGER"),
                ("pages", "VARCHAR(50)"),
                ("selected", "BOOLEAN DEFAULT 0 NOT NULL" if is_sqlite else "BOOLEAN DEFAULT FALSE NOT NULL"),
                ("categories_json", "JSONB" if not is_sqlite else "JSON"),
                ("databases_json", "JSONB" if not is_sqlite else "JSON"),
                ("data_quality_flags_json", "JSONB" if not is_sqlite else "JSON"),  # ← This was missing!
                ("publication_id", "VARCHAR(36)"),
            ]
            
            # Add missing columns
            for col_name, col_type in required_columns:
                if col_name not in existing_columns:
                    try:
                        await conn.execute(text(f"""
                            ALTER TABLE paper 
                            ADD COLUMN {col_name} {col_type}
                        """))
                        migrations_applied.append(col_name)
                        print(f"  ✓ Added column: {col_name}")
                    except Exception as col_error:
                        print(f"  ⚠ Failed to add column {col_name}: {col_error}")
            
            if migrations_applied:
                print(f"✓ Applied {len(migrations_applied)} migrations: {', '.join(migrations_applied)}")
            else:
                print("✓ Database schema is up to date")
                
    except Exception as e:
        print(f"⚠ Migration warning: {e}")
        import traceback
        traceback.print_exc()
        # Don't fail initialization if migrations fail


async def get_db() -> Optional[AsyncSession]:
    """Dependency for getting database session."""
    if _async_session_maker is None:
        yield None
        return
    
    async with _async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def is_db_available() -> bool:
    """Check if database is available."""
    return _async_session_maker is not None
