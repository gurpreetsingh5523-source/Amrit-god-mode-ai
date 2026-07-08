import requests
from typing import Optional, Dict, Any

class ApiClient:
    """HTTP API client for making requests to external services."""
    
    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
    
    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a GET request."""
        try:
            response = self.session.get(
                f"{self.base_url}/{endpoint}",
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"API request failed: {str(e)}")
    
    def post(self, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a POST request."""
        try:
            response = self.session.post(
                f"{self.base_url}/{endpoint}",
                json=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"API request failed: {str(e)}")
    
    def put(self, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a PUT request."""
        try:
            response = self.session.put(
                f"{self.base_url}/{endpoint}",
                json=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"API request failed: {str(e)}")
    
    def delete(self, endpoint: str) -> Dict[str, Any]:
        """Make a DELETE request."""
        try:
            response = self.session.delete(
                f"{self.base_url}/{endpoint}",
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json() if response.text else {"status": "deleted"}
        except requests.exceptions.RequestException as e:
            raise Exception(f"API request failed: {str(e)}")
    
    def close(self):
        """Close the session."""
        self.session.close()