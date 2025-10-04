"""Client for interacting with NASA's public APIs using an API key."""
from __future__ import annotations

from typing import Any, Dict, Optional

import requests

from atlas.config import get_settings

BASE_URL = "https://api.nasa.gov"
IMAGE_LIBRARY_URL = "https://images-api.nasa.gov"


class NASAAPIError(RuntimeError):
    """Raised when the NASA API returns an error response."""


class NASAAPIClient:
    """Thin wrapper around NASA APIs that injects the API key and handles errors."""

    def __init__(self, api_key: Optional[str] = None, timeout: int = 30) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.nasa_api_key or "DEMO_KEY"
        self.timeout = timeout

    def _request(self, method: str, url: str, **kwargs: Any) -> Dict[str, Any]:
        params = kwargs.pop("params", {})
        params.setdefault("api_key", self.api_key)
        response = requests.request(method, url, params=params, timeout=self.timeout, **kwargs)
        if not response.ok:
            raise NASAAPIError(f"NASA API error {response.status_code}: {response.text}")
        return response.json()

    def apod(self, date: Optional[str] = None, **kwargs: Any) -> Dict[str, Any]:
        """Fetch Astronomy Picture of the Day metadata."""
        params = {"date": date} if date else {}
        params.update(kwargs)
        return self._request("GET", f"{BASE_URL}/planetary/apod", params=params)

    def search_images(self, query: str, media_type: str = "image", page: int = 1) -> Dict[str, Any]:
        """Query NASA Image and Video Library for imagery metadata."""
        params = {"q": query, "media_type": media_type, "page": page}
        response = requests.get(f"{IMAGE_LIBRARY_URL}/search", params=params, timeout=self.timeout)
        if not response.ok:
            raise NASAAPIError(f"NASA Image API error {response.status_code}: {response.text}")
        return response.json()

    def osdr_dataset(self, experiment_id: str) -> Dict[str, Any]:
        """Retrieve metadata for an experiment from the Open Science Data Repository."""
        # Placeholder endpoint until official OSDR API contract is finalized.
        url = f"{BASE_URL}/osdr/{experiment_id}"
        return self._request("GET", url)
