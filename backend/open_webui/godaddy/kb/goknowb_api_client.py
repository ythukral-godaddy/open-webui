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


class KBStrategy(str, Enum):
    KNOWB001 = "KNOWB001"
    KNOWB002 = "KNOWB002"
    KNOWB003 = "KNOWB003"


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
    """
    Knowledge Base API Client for interacting with Bedrock KB.

    This client implements the Knowledge Base API OpenAPI 3.1.0 specification.

    Key Features:
    - Health check endpoint
    - KBNode creation with file upload support
    - KBNode management (get, update, delete)
    - Knowledge base search with filtering
    - Automatic file handling and cleanup
    - SSO JWT authentication

    Updated to match OpenAPI spec:
    - Added kbStrategy parameter to create operations
    - Enhanced search validation and filtering
    - Improved error handling and response parsing
    - Added helper methods for collections and documents
    - Better file upload management with proper cleanup
    """

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

    def _generate_request_id(self) -> str:
        """Generate a unique request ID for tracing."""
        return str(uuid.uuid4())[:8]

    def _log_headers(self, request_id: str):
        """Log request headers with sensitive information masked."""
        headers_copy = self.headers.copy()
        if 'Authorization' in headers_copy:
            # Mask the token for security
            auth_header = headers_copy['Authorization']
            if len(auth_header) > 20:
                headers_copy['Authorization'] = f"{auth_header[:15]}...{auth_header[-5:]}"

        log.debug(f"[{request_id}] Request Headers: {headers_copy}")


    def _log_request(self, method: str, url: str, data=None, files=None, request_id=None):
        """Log complete request information across multiple lines with request ID for tracing."""
        if not request_id:
            request_id = self._generate_request_id()

        # Log request header
        log.debug(f"[{request_id}] === REQUEST START ===")
        log.debug(f"[{request_id}] Method: {method}")
        log.debug(f"[{request_id}] URL: {url}")

        # Log request data if present
        if data:
            if isinstance(data, dict):
                log.debug(f"[{request_id}] Request Data: {data}")
            else:
                log.debug(f"[{request_id}] Request Data: {str(data)[:500]}...")

        # Log files if present
        if files:
            log.debug(f"[{request_id}] Files to Upload: {files}")

        log.debug(f"[{request_id}] === REQUEST END ===")
        return request_id

    def _handle_response(self, response: requests.Response, request_id: str = None) -> GoKnowbApiResponse:
        """Handle API response and return status code along with response JSON."""
        try:
            response_data = response.json()
        except ValueError:
            # Handle cases where response is not valid JSON
            response_data = {"error": {
                "message": response.text or "No response content",
                "type": "json_parse_error"
            }}

        # Log response across multiple lines with request ID
        req_id = request_id or "unknown"

        log.debug(f"[{req_id}] === RESPONSE START ===")
        log.debug(f"[{req_id}] Status: {response.status_code} {response.reason}")
        log.debug(f"[{req_id}] URL: {response.url}")

        if not response.ok:
            # Log error details
            if isinstance(response_data, dict) and 'error' in response_data:
                error = response_data['error']
                log.warning(f"[{req_id}] ERROR RESPONSE:")
                log.warning(f"[{req_id}]   Type: {error.get('type', 'Unknown')}")
                log.warning(f"[{req_id}]   Message: {error.get('message', 'No message')}")
                if 'error_code' in error:
                    log.warning(f"[{req_id}]   Error Code: {error.get('error_code')}")
            else:
                log.warning(f"[{req_id}] ERROR RESPONSE: {response_data}")

        log.debug(f"[{req_id}] === RESPONSE END ===")
        return GoKnowbApiResponse(status_code=response.status_code, data=response_data)

    def _is_success(self, response: GoKnowbApiResponse, expected_status: int = 200) -> bool:
        """Check if the response indicates success with expected status code."""
        return response.status_code == expected_status

    def _is_create_success(self, response: GoKnowbApiResponse) -> bool:
        """Check if the create operation was successful (status 202)."""
        return response.status_code == 202

    def _get_error_message(self, response: GoKnowbApiResponse) -> str:
        """Extract error message from response data."""
        if 'error' in response.data:
            error = response.data['error']
            return f"{error.get('type', 'Unknown')}: {error.get('message', 'No message')}"
        return f"HTTP {response.status_code}: {response.data}"

    def health_check(self) -> bool:
        """Check if the service is healthy."""
        url = f"{self.base_url}/health_check"
        request_id = self._log_request("GET", url)
        # Optionally log headers for health check debugging
        # self._log_headers(request_id)

        response = requests.get(url, headers=self.headers)
        result = self._handle_response(response, request_id)
        return result.data.get('healthy', False)

    def create_kbnode_with_file(
            self,
            kb_node_id: str,
            resource_type: KBNodeType,
            files: Optional[List[str]] = None,
            acl: Optional[ACL] = None,
            kb_strategy: KBStrategy = KBStrategy.KNOWB001
    ) -> GoKnowbApiResponse:
        """
        Create a new KBNode with file upload.

        Args:
            kb_node_id: Base identifier for the kbnodes
            resource_type: Type of kbnodes (document or collection)
            files: Optional list of files to upload
            acl: Optional access control list for KBNode
            kb_strategy: Strategy for the KBNode (default: KBStrategy.KNOWB001)
        """

        if not files and resource_type == KBNodeType.DOCUMENT:
            raise ValueError("Files must be provided for document type KBNode")
        data = {
            'kbNodeId': kb_node_id,
            'resourceType': resource_type.value,
            'kbStrategy': kb_strategy.value,
        }

        # Set default ACL if none provided
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
        else:
            # Use default ACL as per API spec
            data['acl'] = """{
                "allowedPrincipals": [
                    {
                        "type": "jomax", 
                        "id": "jomax:JOMAX_ID", 
                        "scope": "read"
                    }
                ]
            }"""

        files_data = None
        if files:
            files_data = [('files', open(f, 'rb')) for f in files]

        # Log request for debugging
        url = f"{self.base_url}/v1/kbnodes"
        request_id = self._log_request("POST", url, data=data, files=files)

        try:
            response = requests.post(
                url,
                headers=self.headers,
                data=data,
                files=files_data
            )
            return self._handle_response(response, request_id)
        finally:
            # Ensure files are closed
            if files_data:
                for _, opened_file in files_data:
                    try:
                        opened_file.close()
                    except Exception as e:
                        log.warning(f"Failed to close file: {e}")

    def create_collection(
            self,
            kb_node_id: str,
            acl: Optional[ACL] = None,
            kb_strategy: KBStrategy = KBStrategy.KNOWB001
    ) -> GoKnowbApiResponse:
        """
        Create a new collection KBNode without files.

        Args:
            kb_node_id: Base identifier for the collection
            acl: Optional access control list for KBNode
            kb_strategy: Strategy for the KBNode (default: KBStrategy.KNOWB001)
        """
        return self.create_kbnode_with_file(
            kb_node_id=kb_node_id,
            resource_type=KBNodeType.COLLECTION,
            files=None,
            acl=acl,
            kb_strategy=kb_strategy
        )

    def create_document(
            self,
            kb_node_id: str,
            files: List[str],
            acl: Optional[ACL] = None,
            kb_strategy: KBStrategy = KBStrategy.KNOWB001
    ) -> GoKnowbApiResponse:
        """
        Create a new document KBNode with files.

        Args:
            kb_node_id: Base identifier for the document
            files: List of file paths to upload (required for documents)
            acl: Optional access control list for KBNode
            kb_strategy: Strategy for the KBNode (default: KBStrategy.KNOWB001)
        """
        if not files:
            raise ValueError("Files are required when creating document KBNodes")

        return self.create_kbnode_with_file(
            kb_node_id=kb_node_id,
            resource_type=KBNodeType.DOCUMENT,
            files=files,
            acl=acl,
            kb_strategy=kb_strategy
        )

    def get_kbnode_details(self, kb_node_id: str) -> GoKnowbApiResponse:
        """Get details of a specific KBNode."""
        url = f"{self.base_url}/v1/kbnodes/{kb_node_id}"
        request_id = self._log_request("GET", url)

        response = requests.get(url, headers=self.headers)
        return self._handle_response(response, request_id)

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

        # Log request for debugging
        url = f"{self.base_url}/v1/kbnodes/{kb_node_id}"
        request_id = self._log_request("PATCH", url, data=data)

        response = requests.patch(url, headers=self.headers, json=data)
        return self._handle_response(response, request_id)

    def delete_kbnode(self, kb_node_id: str) -> GoKnowbApiResponse:
        """Delete a specific KBNode."""
        url = f"{self.base_url}/v1/kbnodes/{kb_node_id}"
        request_id = self._log_request("DELETE", url)

        response = requests.delete(url, headers=self.headers)
        return self._handle_response(response, request_id)

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
            query: Search query string (required, minimum length 1)
            kb_node_ids: List of KBNode IDs to search in (required, at least one entry)
            max_results: Maximum number of results to return (must be > 0, default: 5)
            score_threshold: Minimum score threshold (0-1, default: 0.5)
            search_type: Type of search to perform (default: AUTO)
        """
        # Validate required parameters per API spec
        if not query or len(query.strip()) == 0:
            raise ValueError("Query cannot be empty")

        if not kb_node_ids or len(kb_node_ids) == 0:
            raise ValueError("At least one kbNodeId must be provided")

        if max_results is not None and max_results < 1:
            raise ValueError("maxNumberOfResult must be greater than 0")

        if score_threshold is not None and (score_threshold < 0.0 or score_threshold > 1.0):
            raise ValueError("scoreThreshold must be between 0 and 1")

        # Build request data according to API spec
        data = {
            'query': query.strip(),
            'filter': {
                'kbNodeIds': kb_node_ids,
                'maxNumberOfResult': max_results,
                'scoreThreshold': score_threshold
            },
            'searchType': search_type.value
        }

        # Log request for debugging
        url = f"{self.base_url}/v1/search"
        request_id = self._log_request("POST", url, data=data)

        response = requests.post(url, headers=self.headers, json=data)
        return self._handle_response(response, request_id)
