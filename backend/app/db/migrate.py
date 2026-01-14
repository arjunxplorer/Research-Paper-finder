"""Database migration script to add missing columns."""

import asyncio
from sqlalchemy import text
from app.db.database import _engine, _async_session_maker, is_db_available


async def migrate_database():
    """Add missing columns to existing database tables."""
    if not is_db_available() or _engine is None:
        print("⚠ Database not available, skipping migration")
        return
    
    async with _engine.begin() as conn:
        # Check if publication_date column exists
        try:
            # Try to query the column to see if it exists
            result = await conn.execute(text("PRAGMA table_info(paper)"))
            columns = [row[1] for row in result.fetchall()]
            
            migrations_applied = []
            
            # Add publication_date column if it doesn't exist
            if "publication_date" not in columns:
                print("Adding publication_date column to paper table...")
                await conn.execute(text("""
                    ALTER TABLE paper 
                    ADD COLUMN publication_date DATE
                """))
                migrations_applied.append("publication_date")
            
            # Add other missing columns that might not exist
            if "urls_json" not in columns:
                print("Adding urls_json column to paper table...")
                await conn.execute(text("""
                    ALTER TABLE paper 
                    ADD COLUMN urls_json JSON
                """))
                migrations_applied.append("urls_json")
            
            if "keywords_json" not in columns:
                print("Adding keywords_json column to paper table...")
                await conn.execute(text("""
                    ALTER TABLE paper 
                    ADD COLUMN keywords_json JSON
                """))
                migrations_applied.append("keywords_json")
            
            if "comments" not in columns:
                print("Adding comments column to paper table...")
                await conn.execute(text("""
                    ALTER TABLE paper 
                    ADD COLUMN comments TEXT
                """))
                migrations_applied.append("comments")
            
            if "number_of_pages" not in columns:
                print("Adding number_of_pages column to paper table...")
                await conn.execute(text("""
                    ALTER TABLE paper 
                    ADD COLUMN number_of_pages INTEGER
                """))
                migrations_applied.append("number_of_pages")
            
            if "pages" not in columns:
                print("Adding pages column to paper table...")
                await conn.execute(text("""
                    ALTER TABLE paper 
                    ADD COLUMN pages VARCHAR(50)
                """))
                migrations_applied.append("pages")
            
            if "selected" not in columns:
                print("Adding selected column to paper table...")
                await conn.execute(text("""
                    ALTER TABLE paper 
                    ADD COLUMN selected BOOLEAN DEFAULT 0 NOT NULL
                """))
                migrations_applied.append("selected")
            
            if "categories_json" not in columns:
                print("Adding categories_json column to paper table...")
                await conn.execute(text("""
                    ALTER TABLE paper 
                    ADD COLUMN categories_json JSON
                """))
                migrations_applied.append("categories_json")
            
            if "databases_json" not in columns:
                print("Adding databases_json column to paper table...")
                await conn.execute(text("""
                    ALTER TABLE paper 
                    ADD COLUMN databases_json JSON
                """))
                migrations_applied.append("databases_json")
            
            if "publication_id" not in columns:
                print("Adding publication_id column to paper table...")
                await conn.execute(text("""
                    ALTER TABLE paper 
                    ADD COLUMN publication_id VARCHAR(36)
                """))
                migrations_applied.append("publication_id")
            
            if "data_quality_flags_json" not in columns:
                print("Adding data_quality_flags_json column to paper table...")
                await conn.execute(text("""
                    ALTER TABLE paper 
                    ADD COLUMN data_quality_flags_json JSON
                """))
                migrations_applied.append("data_quality_flags_json")
            
            if migrations_applied:
                print(f"✓ Successfully applied {len(migrations_applied)} migrations: {', '.join(migrations_applied)}")
            else:
                print("✓ Database schema is up to date")
                
        except Exception as e:
            print(f"✗ Migration failed: {e}")
            raise


if __name__ == "__main__":
    # Initialize database first
    from app.db.database import init_db
    asyncio.run(init_db())
    # Then run migrations
    asyncio.run(migrate_database())
