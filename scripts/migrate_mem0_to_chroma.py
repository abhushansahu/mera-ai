#!/usr/bin/env python3
"""Migration script to export memories from Mem0 and import them into Chroma.

Usage:
    python scripts/migrate_mem0_to_chroma.py

This script:
1. Connects to Mem0 (self-hosted or external)
2. Retrieves all memories for all users
3. Imports them into Chroma with the same embeddings
4. Validates the migration

Note: This script assumes both Mem0 and Chroma are configured in your environment.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, List, Any

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.memory_mem0 import Mem0Wrapper
from app.memory_chroma import ChromaMemoryManager
from app.config import settings


async def get_all_mem0_memories(mem0: Mem0Wrapper) -> Dict[str, List[Dict[str, Any]]]:
    """Retrieve all memories from Mem0, grouped by user_id.
    
    Note: Mem0 doesn't have a direct "get all" API, so we use search with
    a very broad query and high limit. This may not capture all memories
    if there are many, but it's the best we can do without direct access
    to Mem0's database.
    
    Args:
        mem0: Mem0Wrapper instance
    
    Returns:
        Dictionary mapping user_id to list of memories
    """
    print("Retrieving memories from Mem0...")
    print("Note: Mem0 doesn't support 'get all', so we'll search with broad queries.")
    print("This may miss some memories if there are many.")
    
    # Try to get memories for common user IDs
    # In practice, you might want to maintain a list of user IDs
    memories_by_user: Dict[str, List[Dict[str, Any]]] = {}
    
    # Try a few common user IDs and broad queries
    test_user_ids = ["default", "user", "obsidian-user", "test"]
    
    # Also try to get user IDs from environment or a config file
    # For now, we'll use a broad search approach
    
    # Search with empty/broad query to get as many memories as possible
    for user_id in test_user_ids:
        try:
            results = await mem0.search(user_id=user_id, query="", limit=1000)
            if results:
                memories_by_user[user_id] = results
                print(f"Found {len(results)} memories for user: {user_id}")
        except Exception as e:
            print(f"Error retrieving memories for {user_id}: {e}")
    
    # If you have a way to get all user IDs, add them here
    # For example, if Mem0 stores user IDs in a database you can access
    
    total_memories = sum(len(mems) for mems in memories_by_user.values())
    print(f"Total memories retrieved: {total_memories}")
    
    return memories_by_user


async def migrate_memories_to_chroma(
    mem0: Mem0Wrapper,
    chroma: ChromaMemoryManager,
    memories_by_user: Dict[str, List[Dict[str, Any]]],
) -> None:
    """Migrate memories from Mem0 to Chroma.
    
    Args:
        mem0: Mem0Wrapper instance
        chroma: ChromaMemoryManager instance
        memories_by_user: Dictionary mapping user_id to list of memories
    """
    print("\nMigrating memories to Chroma...")
    
    total_migrated = 0
    total_errors = 0
    
    for user_id, memories in memories_by_user.items():
        print(f"\nMigrating {len(memories)} memories for user: {user_id}")
        
        for idx, memory in enumerate(memories):
            try:
                text = memory.get("text", "")
                metadata = memory.get("metadata", {})
                
                if not text:
                    print(f"  Skipping memory {idx+1}: empty text")
                    continue
                
                # Store in Chroma
                await chroma.store(
                    user_id=user_id,
                    text=text,
                    metadata=metadata,
                )
                
                total_migrated += 1
                
                if (idx + 1) % 10 == 0:
                    print(f"  Migrated {idx + 1}/{len(memories)} memories...")
                    
            except Exception as e:
                print(f"  Error migrating memory {idx+1}: {e}")
                total_errors += 1
    
    print(f"\nMigration complete!")
    print(f"  Total migrated: {total_migrated}")
    print(f"  Total errors: {total_errors}")


async def validate_migration(
    mem0: Mem0Wrapper,
    chroma: ChromaMemoryManager,
    memories_by_user: Dict[str, List[Dict[str, Any]]],
) -> None:
    """Validate that memories were migrated correctly.
    
    Args:
        mem0: Mem0Wrapper instance
        chroma: ChromaMemoryManager instance
        memories_by_user: Dictionary mapping user_id to list of memories
    """
    print("\nValidating migration...")
    
    validation_errors = 0
    
    for user_id, memories in memories_by_user.items():
        if not memories:
            continue
        
        # Test search with a sample query
        # Use text from first memory as query
        sample_memory = memories[0]
        query_text = sample_memory.get("text", "")[:50]  # First 50 chars
        
        if not query_text:
            continue
        
        try:
            # Search in Chroma
            chroma_results = await chroma.search(
                user_id=user_id,
                query=query_text,
                limit=5,
            )
            
            if chroma_results:
                print(f"  ✓ User {user_id}: Found {len(chroma_results)} results in Chroma")
            else:
                print(f"  ✗ User {user_id}: No results found in Chroma")
                validation_errors += 1
                
        except Exception as e:
            print(f"  ✗ User {user_id}: Validation error: {e}")
            validation_errors += 1
    
    if validation_errors == 0:
        print("\n✓ Validation passed!")
    else:
        print(f"\n✗ Validation found {validation_errors} issues")


async def main():
    """Main migration function."""
    print("=" * 60)
    print("Mem0 to Chroma Migration Script")
    print("=" * 60)
    
    # Check configuration
    if not settings.use_chroma:
        print("\nWarning: USE_CHROMA is not set to 'true'.")
        print("Chroma may not be properly configured.")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != "y":
            print("Migration cancelled.")
            return
    
    # Initialize Mem0
    try:
        print("\nInitializing Mem0...")
        mem0 = Mem0Wrapper()
        print("✓ Mem0 initialized")
    except Exception as e:
        print(f"✗ Failed to initialize Mem0: {e}")
        print("Please check your MEM0_HOST or MEM0_API_KEY configuration.")
        return
    
    # Initialize Chroma
    try:
        print("\nInitializing Chroma...")
        chroma = ChromaMemoryManager(
            host=settings.chroma_host,
            port=settings.chroma_port,
            collection_name=settings.chroma_collection_name,
            persist_directory=settings.chroma_persist_dir,
        )
        print("✓ Chroma initialized")
    except Exception as e:
        print(f"✗ Failed to initialize Chroma: {e}")
        print("Please check your Chroma configuration.")
        return
    
    # Retrieve memories from Mem0
    memories_by_user = await get_all_mem0_memories(mem0)
    
    if not memories_by_user or sum(len(mems) for mems in memories_by_user.values()) == 0:
        print("\nNo memories found to migrate.")
        print("If you expected memories, check:")
        print("  1. Mem0 is running and accessible")
        print("  2. User IDs are correct")
        print("  3. Memories exist in Mem0")
        return
    
    # Confirm migration
    total_memories = sum(len(mems) for mems in memories_by_user.values())
    print(f"\nReady to migrate {total_memories} memories.")
    response = input("Proceed with migration? (y/n): ")
    if response.lower() != "y":
        print("Migration cancelled.")
        return
    
    # Migrate
    await migrate_memories_to_chroma(mem0, chroma, memories_by_user)
    
    # Validate
    await validate_migration(mem0, chroma, memories_by_user)
    
    print("\n" + "=" * 60)
    print("Migration script completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
