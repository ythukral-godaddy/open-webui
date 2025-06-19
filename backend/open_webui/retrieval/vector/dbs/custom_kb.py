from typing import Optional, List, Dict, Union
import logging
import requests
from open_webui.retrieval.vector.main import (
    VectorDBBase,
    VectorItem,
    SearchResult,
    GetResult,
)
from open_webui.env import SRC_LOG_LEVELS


log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])

class CustomKBClient(VectorDBBase):
    def __init__(self):
        pass

    def has_collection(self, collection_name: str) -> bool:
        raise Exception("vector DB invoked")


    def delete_collection(self, collection_name: str):
        raise Exception("vector DB invoked")


    def insert(self, collection_name: str, items: List[VectorItem]):
        raise Exception("vector DB invoked")


    def upsert(self, collection_name: str, items: List[VectorItem]):
        raise Exception("vector DB invoked")

    def search(
        self, collection_name: str, vectors: List[List[Union[float, int]]], limit: int
    ) -> Optional[SearchResult]:
        raise Exception("vector DB invoked")


    def query(
        self, collection_name: str, filter: Dict, limit: Optional[int] = None
    ) -> Optional[GetResult]:
        raise Exception("vector DB invoked")


    def get(self, collection_name: str) -> Optional[GetResult]:
        raise Exception("vector DB invoked")

    def delete(
        self,
        collection_name: str,
        ids: Optional[List[str]] = None,
        filter: Optional[Dict] = None,
    ) -> None:
        raise Exception("vector DB invoked")
