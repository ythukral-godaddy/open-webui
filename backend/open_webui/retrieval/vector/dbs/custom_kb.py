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
from open_webui.config import GOKNOWB_API_URL, GOKNOWB_API_KEY

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])

class CustomKBClient(VectorDBBase):
    def __init__(self):
        self.api_url = GOKNOWB_API_URL
        self.api_key = GOKNOWB_API_KEY
        self.headers = {
            "Authorization": f"sso-jwt {self.api_key}"
        }

    def _make_request(self, method, endpoint, **kwargs):
        url = f"{self.api_url}{endpoint}"
        try:
            response = requests.request(method, url, headers=self.headers, **kwargs)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            log.error(f"API request failed: {e}")
            raise

    def has_collection(self, collection_name: str) -> bool:
        try:
            self._make_request("GET", f"/v1/kbnodes/{collection_name}")
            return True
        except Exception:
            return False

    def delete_collection(self, collection_name: str):
        try:
            self._make_request("DELETE", f"/v1/kbnodes/{collection_name}")
        except Exception as e:
            log.error(f"Error deleting collection: {e}")

    def insert(self, collection_name: str, items: List[VectorItem]):
        try:
            # Convert items to files and metadata
            files = []
            for item in items:
                # Here we assume the text content is the file content
                # You may need to adjust this based on your actual data format
                files.append(('files', (f"{item.id}.txt", item.text.encode(), 'text/plain')))
            
            data = {
                'kbNodeId': collection_name,
                'resourceType': 'document',
                'acl': {
                    'allowedPrincipals': [
                        {
                            'type': 'jomax',
                            'id': '*',
                            'scope': 'read'
                        }
                    ]
                }
            }
            
            self._make_request("POST", "/v1/kbnodes", files=files, data={'data': data})
        except Exception as e:
            log.error(f"Error inserting items: {e}")

    def upsert(self, collection_name: str, items: List[VectorItem]):
        # Since the API doesn't have a direct upsert endpoint,
        # we'll try to insert and handle any conflicts
        self.insert(collection_name, items)

    def search(
        self, collection_name: str, vectors: List[List[Union[float, int]]], limit: int
    ) -> Optional[SearchResult]:
        try:
            # Convert vectors to query
            # Note: Your API uses text queries rather than vectors directly
            # You'll need to adjust this based on your actual search requirements
            search_request = {
                "query": " ".join(map(str, vectors[0][:10])),  # Using first few vector components as query
                "filter": {
                    "kbNodeIds": [collection_name],
                    "maxNumberOfResult": limit,
                    "scoreThreshold": 0.0
                },
                "searchType": "semantic"
            }
            
            response = self._make_request("POST", "/v1/search", json=search_request)
            
            results = []
            for result in response.get("results", []):
                results.append({
                    "id": result["location"]["kbNodeId"],
                    "score": result["score"],
                    "text": result["content"]["text"],
                    "metadata": {}
                })
            
            return SearchResult(results=results)
        except Exception as e:
            log.error(f"Error searching vectors: {e}")
            return None

    def query(
        self, collection_name: str, filter: Dict, limit: Optional[int] = None
    ) -> Optional[GetResult]:
        try:
            response = self._make_request("GET", f"/v1/kbnodes/{collection_name}")
            kbnode = response["kbNode"]
            
            results = []
            if kbnode["resourceType"] == "document":
                results.append({
                    "id": kbnode["kbNodeId"],
                    "text": "",  # The API doesn't return the actual text content
                    "metadata": {
                        "status": kbnode["status"],
                        "owner": kbnode["owner"],
                        "created_at": kbnode["createdAt"],
                        "updated_at": kbnode["updatedAt"]
                    }
                })
            elif kbnode["resourceType"] == "collection" and kbnode.get("children"):
                for child in kbnode["children"]:
                    results.append({
                        "id": child["kbNodeId"],
                        "text": "",  # The API doesn't return the actual text content
                        "metadata": {
                            "status": child["status"],
                            "owner": child["owner"],
                            "created_at": child["createdAt"],
                            "updated_at": child["updatedAt"]
                        }
                    })
            
            return GetResult(results=results[:limit] if limit else results)
        except Exception as e:
            log.error(f"Error querying with filter: {e}")
            return None

    def get(self, collection_name: str) -> Optional[GetResult]:
        return self.query(collection_name, {})

    def delete(
        self,
        collection_name: str,
        ids: Optional[List[str]] = None,
        filter: Optional[Dict] = None,
    ) -> None:
        try:
            if ids:
                for id in ids:
                    self._make_request("DELETE", f"/v1/kbnodes/{id}")
            else:
                self._make_request("DELETE", f"/v1/kbnodes/{collection_name}")
        except Exception as e:
            log.error(f"Error deleting vectors: {e}") 