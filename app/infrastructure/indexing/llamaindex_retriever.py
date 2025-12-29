"""LlamaIndex retriever wrapped as LangChain BaseRetriever."""

from typing import List, Optional

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from app.infrastructure.indexing.obsidian_indexer import ObsidianIndexer


class LlamaIndexRetriever(BaseRetriever):
    """LangChain retriever wrapper for LlamaIndex Obsidian vault index."""

    indexer: ObsidianIndexer
    k: int = 5

    def __init__(
        self,
        indexer: Optional[ObsidianIndexer] = None,
        vault_path: Optional[str] = None,
        k: int = 5,
        **kwargs,
    ) -> None:
        """Initialize LlamaIndexRetriever.
        
        Args:
            indexer: ObsidianIndexer instance (creates one if not provided)
            vault_path: Path to Obsidian vault (required if indexer not provided)
            k: Number of documents to retrieve
        """
        super().__init__(**kwargs)
        if indexer is None:
            if vault_path is None:
                raise ValueError("Either indexer or vault_path must be provided")
            indexer = ObsidianIndexer(vault_path=vault_path)
        self.indexer = indexer
        self.k = k

    def _get_relevant_documents(self, query: str) -> List[Document]:
        """Synchronous retrieval (not recommended for async)."""
        import asyncio
        return asyncio.run(self._aget_relevant_documents(query))

    async def _aget_relevant_documents(self, query: str) -> List[Document]:
        """Asynchronous retrieval from LlamaIndex."""
        # Get or build index
        index = self.indexer.get_index()
        
        # Create retriever from index
        retriever = index.as_retriever(similarity_top_k=self.k)
        
        # Retrieve nodes
        nodes = retriever.retrieve(query)
        
        # Convert to LangChain Documents
        documents = []
        for node in nodes:
            doc = Document(
                page_content=node.text,
                metadata={
                    "source": "obsidian",
                    "file_path": getattr(node, "file_path", ""),
                    "file_name": getattr(node, "file_name", ""),
                    **node.metadata,
                },
            )
            documents.append(doc)
        
        return documents
