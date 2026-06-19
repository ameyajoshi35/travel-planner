import os
from tavily import TavilyClient

_client = None


def _get_client() -> TavilyClient:
    global _client
    if _client is None:
        _client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    return _client


def search(query: str, max_results: int = 5, include_images: bool = True) -> dict:
    response = _get_client().search(query, max_results=max_results, include_images=include_images)
    results = response.get("results", [])
    images = [
        img for img in response.get("images", [])
        if isinstance(img, str) and img.startswith("https")
    ]
    return {"results": results, "images": images}
