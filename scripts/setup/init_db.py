#!/usr/bin/env python3
"""Initialize the crawler database directly using SQLAlchemy."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from crawler.database.models import Base
from crawler.database.connection import get_database_manager


async def init_database():
    """Initialize the database with all tables."""
    try:
        db_manager = get_database_manager()
        
        print("Creating database tables...")
        
        # Create all tables
        async with db_manager.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # Setup database optimizations
        await db_manager.setup_database()
        
        print(f"✅ Database initialized successfully at: {db_manager.database_url}")
        
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")
        sys.exit(1)
    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(init_database()) 