from enum import Enum
from typing import List, Optional, Dict, Any, Union
import requests
import time
import uuid
import logging
from dataclasses import dataclass
from datetime import datetime
from open_webui.config import GOKNOWB_API_URL, GOKNOWB_API_KEY
from open_webui.env import (
    SRC_LOG_LEVELS
)

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])

class PrincipalType(str, Enum):
    JOMAX = "jomax"
    IAM = "iam"
    ADGROUP = "adgroup"
    ANY = "*"


class ScopeType(str, Enum):
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


class KBNodeType(str, Enum):
    DOCUMENT = "document"
    COLLECTION = "collection"


class SearchType(str, Enum):
    LEXICAL_AND_SEMANTIC = "lexical_and_semantic"
    SEMANTIC = "semantic"
    AUTO = "auto"


@dataclass
class AllowedPrincipal:
    id: str
    type: PrincipalType
    scope: ScopeType


@dataclass
class ACL:
    allowed_principals: List[AllowedPrincipal]


@dataclass
class GoKnowbApiResponse:
    status_code: int
    data: Dict[str, Any]


class KnowledgeBaseClient:
    # Hardcoded configuration
    BASE_URL = GOKNOWB_API_URL
    
    def __init__(self):
        """
        Initialize the Knowledge Base API client.
        
        No arguments required - uses hardcoded configuration and internal token generation.
        """
        self.base_url = self.BASE_URL.rstrip('/')
        # Generate token internally
        sso_jwt_token = self._generate_token()
        self.headers = {
            "Authorization": f"sso-jwt {sso_jwt_token}"
        }
    
    def _generate_token(self) -> str:
        """
        Generate a fresh SSO JWT token.
        
        This method should be implemented based on your authentication requirements.
        For now, it's a placeholder that should be customized for your environment.
        
        Returns:
            str: Fresh SSO JWT token
        """
        # TODO YATIN: Implement your token generation logic here
        # Examples:
        # 1. Call OAuth endpoint with client credentials
        # 2. Use service account credentials
        # 3. Read from secure token store
        # 4. Generate JWT with signing key
        
        # Placeholder implementation - replace with actual logic
        demo_token = GOKNOWB_API_KEY
        
        # Example of what a real implementation might look like:
        # try:
        #     import os
        #     response = requests.post(
        #         "https://auth.godaddy.com/oauth/token",
        #         data={
        #             "grant_type": "client_credentials",
        #             "client_id": os.getenv("CLIENT_ID"),
        #             "client_secret": os.getenv("CLIENT_SECRET"),
        #             "scope": "kb:read kb:write"
        #         }
        #     )
        #     return response.json()["access_token"]
        # except Exception as e:
        #     print(f"Token generation failed: {e}")
        #     raise
        
        return demo_token

    def _handle_response(self, response: requests.Response) -> GoKnowbApiResponse:
        """Handle API response and return status code along with response JSON."""
        try:
            response_data = response.json()
        except ValueError:
            # Handle cases where response is not valid JSON
            response_data = {"error": {
                "message": response.text or "No response content",
                "type": "json_parse_error"
            }}
        
        if not response.ok:
            error_message = response_data.get('error', {}).get('message', 'Unknown error') if isinstance(response_data, dict) else str(response_data)
            log.debug(f"API Error ({response.status_code}): {error_message}")
        
        return GoKnowbApiResponse(status_code=response.status_code, data=response_data)

    def health_check(self) -> bool:
        """Check if the service is healthy."""
        response = requests.get(f"{self.base_url}/health_check", headers=self.headers)
        result = self._handle_response(response)
        return result.data.get('healthy', False)

    def create_kbnode_with_file(
        self,
        kb_node_id: str,
        resource_type: KBNodeType,
        files: Optional[List[str]] = None,
        acl: Optional[ACL] = None
    ) -> GoKnowbApiResponse:
        """
        Create a new KBNode with file upload.
        
        Args:
            kb_node_id: Base identifier for the kbnodes
            resource_type: Type of kbnodes (document or collection)
            files: Optional list of files to upload
            acl: Optional access control list for KBNode
        """

        if not files and resource_type == KBNodeType.DOCUMENT:
            raise ValueError("Files must be provided for document type KBNode")
        data = {
            'kbNodeId': kb_node_id,
            'resourceType': resource_type.value,
        }
        
        if acl:
            data['acl'] = {
                'allowedPrincipals': [
                    {
                        'id': p.id,
                        'type': p.type.value,
                        'scope': p.scope.value
                    }
                    for p in acl.allowed_principals
                ]
            }

        files_data = None
        if files:
            files_data = [('files', open(f, 'rb')) for f in files]

        response = requests.post(
            f"{self.base_url}/v1/kbnodes",
            headers=self.headers,
            data=data,
            files=files_data
        )
        return self._handle_response(response)

    def get_kbnode_details(self, kb_node_id: str) -> GoKnowbApiResponse:
        """Get details of a specific KBNode."""
        response = requests.get(
            f"{self.base_url}/v1/kbnodes/{kb_node_id}",
            headers=self.headers
        )
        return self._handle_response(response)

    def update_kbnode(self, kb_node_id: str, acl: ACL) -> GoKnowbApiResponse:
        """
        Update a KBNode's visibility.
        
        Args:
            kb_node_id: ID of the KBNode to update
            acl: New access control list configuration
        """
        data = {
            'acl': {
                'allowedPrincipals': [
                    {
                        'id': p.id,
                        'type': p.type.value,
                        'scope': p.scope.value
                    }
                    for p in acl.allowed_principals
                ]
            }
        }
        
        response = requests.patch(
            f"{self.base_url}/v1/kbnodes/{kb_node_id}",
            headers=self.headers,
            json=data
        )
        return self._handle_response(response)

    def delete_kbnode(self, kb_node_id: str) -> GoKnowbApiResponse:
        """Delete a specific KBNode."""
        response = requests.delete(
            f"{self.base_url}/v1/kbnodes/{kb_node_id}",
            headers=self.headers
        )
        return self._handle_response(response)

    def search_kb(
        self,
        query: str,
        kb_node_ids: List[str],
        max_results: Optional[int] = 5,
        score_threshold: Optional[float] = 0.5,
        search_type: SearchType = SearchType.AUTO
    ) -> GoKnowbApiResponse:
        """
        Search the knowledge base.
        
        Args:
            query: Search query string
            kb_node_ids: List of KBNode IDs to search in
            max_results: Maximum number of results to return
            score_threshold: Minimum score threshold (0-1)
            search_type: Type of search to perform
        """
        data = {
            'query': query,
            'filter': {
                'kbNodeIds': kb_node_ids,
                'maxNumberOfResult': max_results,
                'scoreThreshold': score_threshold
            },
            'searchType': search_type.value
        }
        
        response = requests.post(
            f"{self.base_url}/v1/search",
            headers=self.headers,
            json=data
        )
        return self._handle_response(response)
