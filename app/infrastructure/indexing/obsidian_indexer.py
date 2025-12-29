"""LlamaIndex-based Obsidian vault indexer."""

import os
from pathlib import Path
from typing import Optional

from llama_index.core import VectorStoreIndex, StorageContext, Settings
from llama_index.core.node_parser import SimpleNodeParser
from llama_index.vector_stores.chroma import ChromaVectorStore

try:
    from llama_index.readers.obsidian import ObsidianReader
except ImportError:
    # ObsidianReader may not be available in all llama-index versions
    # Fallback to a simple file reader
    ObsidianReader = None
import chromadb
from chromadb.config import Settings as ChromaSettings

from app.infrastructure.config.settings import get_settings


class ObsidianIndexer:
    """Index Obsidian vault using LlamaIndex with Chroma as vector store."""

    def __init__(
        self,
        vault_path: Optional[str] = None,
        collection_name: str = "obsidian_vault",
        persist_directory: Optional[str] = None,
    ) -> None:
        """Initialize Obsidian indexer.
        
        Args:
            vault_path: Path to Obsidian vault directory
            collection_name: Chroma collection name for the index
            persist_directory: Directory for Chroma persistence
        """
        settings = get_settings()
        
        self.vault_path = vault_path or os.getenv("OBSIDIAN_VAULT_PATH")
        if not self.vault_path:
            raise ValueError("OBSIDIAN_VAULT_PATH must be set or provided")
        
        self.collection_name = collection_name
        self.persist_directory = persist_directory or settings.chroma_persist_dir or "./chroma_db"
        
        # Initialize Chroma client
        self._chroma_client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        
        # Get or create Chroma collection
        self._chroma_collection = self._chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        
        # Create Chroma vector store
        self._vector_store = ChromaVectorStore(chroma_collection=self._chroma_collection)
        
        self._index: Optional[VectorStoreIndex] = None

    def build_index(self) -> VectorStoreIndex:
        """Build or rebuild the Obsidian vault index.
        
        Returns:
            VectorStoreIndex instance
        """
        if ObsidianReader is None:
            raise ImportError(
                "llama_index.readers.obsidian is not available. "
                "Install it with: pip install llama-index-readers-obsidian"
            )
        
        # Load Obsidian vault using LlamaIndex reader
        reader = ObsidianReader(input_dir=self.vault_path)
        documents = reader.load_data()
        
        # Create storage context with Chroma vector store
        storage_context = StorageContext.from_defaults(
            vector_store=self._vector_store,
        )
        
        # Create index from documents
        index = VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context,
            show_progress=True,
        )
        
        self._index = index
        return index

    def load_index(self) -> Optional[VectorStoreIndex]:
        """Load existing index from Chroma.
        
        Returns:
            VectorStoreIndex instance or None if index doesn't exist
        """
        try:
            storage_context = StorageContext.from_defaults(
                vector_store=self._vector_store,
            )
            index = VectorStoreIndex.from_vector_store(
                vector_store=self._vector_store,
                storage_context=storage_context,
            )
            self._index = index
            return index
        except Exception:
            return None

    def get_index(self) -> VectorStoreIndex:
        """Get index, building it if necessary.
        
        Returns:
            VectorStoreIndex instance
        """
        if self._index is not None:
            return self._index
        
        # Try to load existing index
        index = self.load_index()
        if index is not None:
            return index
        
        # Build new index
        return self.build_index()

    def update_index(self, file_paths: Optional[list[str]] = None) -> VectorStoreIndex:
        """Update index with new or changed files.
        
        Args:
            file_paths: Optional list of specific file paths to update
            
        Returns:
            Updated VectorStoreIndex instance
        """
        # For now, rebuild the entire index
        # In the future, could implement incremental updates
        return self.build_index()

    def refresh_index(self) -> VectorStoreIndex:
        """Refresh (rebuild) the entire index.
        
        Returns:
            Refreshed VectorStoreIndex instance
        """
        return self.build_index()
