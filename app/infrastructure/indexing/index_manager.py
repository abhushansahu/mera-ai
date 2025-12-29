"""Index management for Obsidian vault."""

import os
from pathlib import Path
from typing import Optional

from app.infrastructure.indexing.obsidian_indexer import ObsidianIndexer
from app.infrastructure.config.settings import get_settings


class IndexManager:
    """Manage Obsidian vault indexing operations."""

    def __init__(self, vault_path: Optional[str] = None) -> None:
        """Initialize index manager.
        
        Args:
            vault_path: Path to Obsidian vault (uses settings if not provided)
        """
        settings = get_settings()
        self.vault_path = vault_path or settings.obsidian_vault_path
        if not self.vault_path:
            raise ValueError("OBSIDIAN_VAULT_PATH must be set or provided")
        
        self.indexer = ObsidianIndexer(vault_path=self.vault_path)

    def build_index(self) -> None:
        """Build initial index from Obsidian vault.
        
        This creates a new index, replacing any existing one.
        """
        print(f"Building index for Obsidian vault: {self.vault_path}")
        index = self.indexer.build_index()
        print(f"✓ Index built successfully with {len(index.storage_context.docstore.docs)} documents")

    def update_index(self, file_paths: Optional[list[str]] = None) -> None:
        """Update index with new or changed files.
        
        Args:
            file_paths: Optional list of specific file paths to update
        """
        if file_paths:
            print(f"Updating index for {len(file_paths)} files")
        else:
            print("Updating index (full rebuild)")
        
        index = self.indexer.update_index(file_paths=file_paths)
        print(f"✓ Index updated successfully")

    def refresh_index(self) -> None:
        """Refresh (rebuild) the entire index."""
        print(f"Refreshing index for Obsidian vault: {self.vault_path}")
        index = self.indexer.refresh_index()
        print(f"✓ Index refreshed successfully with {len(index.storage_context.docstore.docs)} documents")

    def load_index(self) -> bool:
        """Load existing index if available.
        
        Returns:
            True if index was loaded, False otherwise
        """
        index = self.indexer.load_index()
        if index is not None:
            print("✓ Existing index loaded")
            return True
        print("✗ No existing index found")
        return False


def main() -> None:
    """CLI entry point for index management."""
    import argparse

    parser = argparse.ArgumentParser(description="Manage Obsidian vault index")
    parser.add_argument(
        "command",
        choices=["build", "update", "refresh", "load"],
        help="Command to execute",
    )
    parser.add_argument(
        "--vault-path",
        type=str,
        help="Path to Obsidian vault (overrides OBSIDIAN_VAULT_PATH)",
    )
    parser.add_argument(
        "--files",
        nargs="+",
        help="Specific files to update (for update command)",
    )

    args = parser.parse_args()

    try:
        manager = IndexManager(vault_path=args.vault_path)

        if args.command == "build":
            manager.build_index()
        elif args.command == "update":
            manager.update_index(file_paths=args.files)
        elif args.command == "refresh":
            manager.refresh_index()
        elif args.command == "load":
            manager.load_index()
    except ValueError as e:
        print(f"Error: {e}")
        print("Set OBSIDIAN_VAULT_PATH environment variable or use --vault-path")
        exit(1)
    except Exception as e:
        print(f"Error: {e}")
        exit(1)


if __name__ == "__main__":
    main()
