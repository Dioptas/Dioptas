"""
Initialize the database by creating all tables.

!!!!!!!!!!!!!!!!!!!Run this script once before starting the application for the first time!!!!!!!!!!!!!!!!!!
joking, it's gonna run anyway. docker will take care of everything
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from app.database import init_db, engine
from app.models import Base

def main():
    """Initialize database tables"""
    print("Initializing database...")
    print(f"Database URL: {engine.url}")
    
    try:
        # Create all tables
        init_db()
        
        # Verify tables were created
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        print("\n✓ Database initialized successfully!")
        print(f"\nCreated tables:")
        for table in sorted(tables):
            print(f"  - {table}")
        
        print("\nYou can now:")
        print("  1. Import JCPDS files: python scripts/import_jcpds.py <directory>")
        print("  2. Start the API server: uvicorn app.main:app --reload")
        
    except Exception as e:
        print(f"\n✗ Error initializing database: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
