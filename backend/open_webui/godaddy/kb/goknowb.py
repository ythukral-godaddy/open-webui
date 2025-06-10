import logging
import uuid
import threading
from typing import List, Optional, Dict, Any, Union
from open_webui.retrieval.vector.main import SearchResult
from open_webui.models.files import FileModel, Files
from .goknowb_api_client import (
    KnowledgeBaseClient,
    PrincipalType,
    ScopeType,
    KBNodeType,
    SearchType,
    AllowedPrincipal,
    ACL, GoKnowbApiResponse
)
from ...retrieval.vector.main import SearchResult, GetResult, VectorItem
from open_webui.env import (
    SRC_LOG_LEVELS
)

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])


class GoKnowbWrapper:
    """
    Wrapper/Proxy class for GoDaddy Knowledge Base API.
    
    This class provides error handling and logging on top of the raw API client
    while maintaining the same interface. Uses singleton pattern for instance management.
    """
    BASE_COLLECTION_NAME = "open_webui"
    _instance = None
    _lock = threading.Lock()
    _initialized = False
    
    def __new__(cls):
        """Create or return the singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(GoKnowbWrapper, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """
        Initialize the GoKnowB wrapper.
        
        No arguments required - uses hardcoded configuration and internal token generation.
        """
        # Only initialize once
        if not self._initialized:
            self.client = KnowledgeBaseClient()
            GoKnowbWrapper._initialized = True
    
    @classmethod
    def get_instance(cls) -> 'GoKnowbWrapper':
        """
        Get the singleton instance of GoKnowBWrapper.
        
        No arguments required - uses hardcoded configuration and internal token generation.
        
        Returns:
            GoKnowbWrapper: The singleton instance
        """
        if cls._instance is None:
            return cls()
        return cls._instance
    
    @classmethod
    def reset_instance(cls):
        """Reset the singleton instance (useful for testing)."""
        with cls._lock:
            cls._instance = None
            cls._initialized = False
        
    def health_check(self) -> bool:
        """Check if the service is healthy."""
        try:
            result = self.client.health_check()
            log.debug(f"Health check result: {result}")
            return result
        except Exception as e:
            log.error(f"Health check failed: {e}")
            raise


    def update_collection_name(self, collection_name: str) -> str:
        """Update the collection name to ensure it is valid."""
        if collection_name is None or collection_name == "":
            collection_name = self.BASE_COLLECTION_NAME
        elif self.BASE_COLLECTION_NAME is None or self.BASE_COLLECTION_NAME == "":
            raise ValueError("Base collection name is not set. Please set BASE_COLLECTION_NAME.")
        elif not collection_name.startswith(self.BASE_COLLECTION_NAME):
            # Ensure the collection name starts with the base collection name
            collection_name = f"{self.BASE_COLLECTION_NAME}/{collection_name}"
        return collection_name

    def has_collection(self, collection_name: str) -> bool:
        """Check if the collection exists in the vector DB."""
        try:
            collection_name = self.update_collection_name(collection_name)
            result = self.client.get_kbnode_details(collection_name)
            if result.status_code==404 and result.get("error"):
                log.debug(f"Collection {collection_name} does not exist: {result['error']}")
                return False
            elif result.status_code==200:
                log.debug(f"Collection {collection_name} exists.")
                return True
            else:
                raise Exception(f" API response: {result}")
        except Exception as e:
            log.error(f"Failed to get details for collection_name {collection_name}: {e}")
            raise

    def delete_collection(self, collection_name: str) -> None:
        """Delete a collection from the vector DB."""
        try:
            collection_name = self.update_collection_name(collection_name)
            result = self.client.delete_kbnode(collection_name)
            if result.status_code != 200:
                raise Exception(f" API response: {result}")
            log.debug(f"Successfully deleted collection_name: {collection_name}")

        except Exception as e:
            log.error(f"Failed to delete collection_name {collection_name}: {e}")
            raise

    def insert(self, collection_name: str, file_full_name: str) -> None:
        """Insert a list of vector items into a collection."""
        collection_name = self.update_collection_name(collection_name)
        try:
            result = self.client.create_kbnode_with_file(
                kb_node_id=collection_name,
                resource_type=collection_name,
                files=[file_full_name]
            )
            log.info(f"Successfully created file: {collection_name}/{file_full_name}")
            return result
        except Exception as e:
            log.error(f"Failed to create file {collection_name}/{file_full_name}: {e}")
            raise
        pass

    def upsert(self, collection_name: str, items: List[VectorItem]) -> None:
        """Insert or update vector items in a collection."""
        pass

    def _create_search_result_from_response(goknowb_response: GoKnowbApiResponse) -> SearchResult:
        """
        Convert GoKnowB API response to SearchResult object.

        Args:
            response_data: The JSON response from GoKnowB search API

        Returns:
            SearchResult: Formatted search result object
        """

        if goknowb_response.status_code != 200:
            # Handle error case - return empty SearchResult
            return None

        response_data = goknowb_response.data
        results = response_data.get("results", [])

        # Extract data from each result item

        ids = []
        documents = []
        metadatas = []
        distances = []

        for result in results:
            # Extract document ID from location
            kb_node_id = result.get("location", {}).get("kbNodeId", "")
            id = str(uuid.uuid4())
            ids.append(id)

            # Extract text content
            content = result.get("content", {})
            text = content.get("text", "")
            documents.append(text)

            # Create metadata object

            filename = kb_node_id.split("/")[-1]
            file_id = filename.split("_")[0]
            file = Files.get_file_by_id(file_id)
            metadata = {
                **file.meta,
                "name": file.filename,
                "created_by": file.user_id,
                "file_id": file.id,
                "source": file.filename,
            }
            metadatas.append(metadata)
            # Extract score (distance)
            score = result.get("score", 0.0)
            distances.append(score)

        # Create SearchResult object
        search_result = SearchResult(
            ids=[ids],  # Wrapped in list for consistency with vector DB format
            documents=[documents],  # Wrapped in list for consistency
            metadatas=[metadatas],  # Wrapped in list for consistency
            distances=[distances]  # List of distances for each result
        )

        return search_result


    def search(
            self, collection_names: list[str],
            query: str,
            limit: Optional[int] = 5,
            score_threshold: Optional[float] = 0.5,
            search_type: SearchType = SearchType.SEMANTIC
    ) -> Optional[SearchResult]:
        """Search for similar vectors in a collection."""
        try:
            kb_node_ids = []
            if not collection_names or len(collection_names) == 0:
                raise ValueError("Collection names cannot be empty or None.")
            for collection_name in collection_names:
                kb_node_ids.append(self.update_collection_name(collection_name))
            result = self.client.search_kb(
                query=query,
                kb_node_ids=kb_node_ids,
                max_results=limit,
                score_threshold=score_threshold,
                search_type=search_type
            )
            log.debug(f"Search completed for query: {query[:50]}...")
            return self._create_search_result_from_response(result)
        except Exception as e:
            log.error(f"Search failed for query '{query}': {e}")
            return None


    def queryByCollectionNameAndFileId(
            self, collection_name: str, file_full_name: str, limit: Optional[int] = None
    ) -> Optional[GetResult]:
        """Query vectors from a collection using metadata filter."""
        collection_name = self.update_collection_name(collection_name)
        # TODO YATIN: implement when we have provision to fetch all doc for a file in a collection


        pass
    def query(
            self, collection_name: str, filter: Dict, limit: Optional[int] = None
    ) -> Optional[GetResult]:
        """Query vectors from a collection using metadata filter."""
        pass

    def get(self, collection_name: str) -> Optional[GetResult]:
        """Retrieve all vectors from a collection."""
        collection_name = self.update_collection_name(collection_name)
        # TODO YATIN: implement when we have provision to fetch all doc for a collection
        pass

    def delete(
            self,
            collection_name: str,
            ids: Optional[List[str]] = None,
            filter: Optional[Dict] = None,
    ) -> None:
        """Delete vectors by ID or filter from a collection."""
        collection_name = self.update_collection_name(collection_name)
        pass

    def reset(self) -> None:
        """Reset the vector database by removing all collections or those matching a condition."""
        try:
            collection_name = self.update_collection_name(None)
            result = self.client.delete_kbnode(collection_name)
            if result.status_code != 200:
                raise Exception(f" API response: {result}")
            log.debug(f"Reset Successful. Deleted collection_name: {collection_name}")
        except Exception as e:
            log.error(f"Failed to delete collection_name {collection_name}: {e}")
            raise


    # def update_kbnode(self, kb_node_id: str, acl: ACL) -> Dict[str, Any]:
    #     """
    #     Update a KBNode's visibility.
    #
    #     Args:
    #         kb_node_id: ID of the KBNode to update
    #         acl: New access control list configuration
    #     """
    #     try:
    #         result = self.client.update_kbnode(kb_node_id, acl)
    #         log.info(f"Successfully updated KBNode: {kb_node_id}")
    #         return result
    #     except Exception as e:
    #         log.error(f"Failed to update KBNode {kb_node_id}: {e}")
    #         raise
    #
    # def delete_kbnode(self, kb_node_id: str) -> Dict[str, Any]:
    #     """Delete a specific KBNode."""
    #     try:
    #         result = self.client.delete_kbnode(kb_node_id)
    #         log.info(f"Successfully deleted KBNode: {kb_node_id}")
    #         return result
    #     except Exception as e:
    #         log.error(f"Failed to delete KBNode {kb_node_id}: {e}")
    #         raise


# Convenience function for getting the singleton wrapper instance
def create_goknowb_client() -> GoKnowbWrapper:
    """
    Factory function to get the singleton GoKnowB wrapper instance.
    
    No arguments required - uses hardcoded configuration and internal token generation.
    
    Returns:
        GoKnowbWrapper: The singleton instance
    """
    return GoKnowbWrapper.get_instance()
