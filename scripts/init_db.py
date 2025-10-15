#!/usr/bin/env python3
"""
Database initialization script

Creates database tables and optionally seeds initial data.
"""
import sys
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from src.auth.models import Base
from src.utils import load_config


async def init_database(config_path: str = "config/config.yaml", drop_existing: bool = False):
    """
    Initialize database tables

    Args:
        config_path: Path to configuration file
        drop_existing: If True, drop existing tables before creating
    """
    print("=" * 60)
    print("HPSDR Proxy - Database Initialization")
    print("=" * 60)

    # Load configuration
    try:
        config = load_config(config_path)
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return False

    # Get database connection string
    db_config = config.database
    connection_string = db_config.get_connection_string()

    print(f"\nDatabase type: {db_config.type}")
    print(f"Connection: {connection_string.split('@')[-1] if '@' in connection_string else connection_string}")

    try:
        # Create async engine
        engine = create_async_engine(connection_string, echo=True)

        async with engine.begin() as conn:
            if drop_existing:
                print("\nDropping existing tables...")
                await conn.run_sync(Base.metadata.drop_all)
                print("✓ Existing tables dropped")

            print("\nCreating tables...")
            await conn.run_sync(Base.metadata.create_all)
            print("✓ Tables created successfully")

        await engine.dispose()

        print("\n" + "=" * 60)
        print("Database initialization complete!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Copy config/config.yaml.example to config/config.yaml")
        print("2. Edit config/config.yaml with your settings")
        print("3. Run: python main.py")
        print("\nDefault admin credentials:")
        print("  Username: admin")
        print("  Password: admin123")
        print("  ⚠️  CHANGE THIS PASSWORD IMMEDIATELY!")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n❌ Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Initialize HPSDR Proxy database')
    parser.add_argument(
        '-c', '--config',
        default='config/config.yaml',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--drop',
        action='store_true',
        help='Drop existing tables before creating (⚠️ DANGEROUS!)'
    )

    args = parser.parse_args()

    # Confirm drop if requested
    if args.drop:
        print("\n⚠️  WARNING: This will DELETE ALL EXISTING DATA!")
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            return

    # Run initialization
    success = asyncio.run(init_database(args.config, args.drop))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
