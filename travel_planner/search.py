"""
Search layer — backed by LangChain Community's TavilySearchAPIWrapper.

TavilySearchAPIWrapper is LangChain's official integration for the Tavily
search API. raw_results() returns the full API response including images,
which we use for destination photo fetching.

The wrapper reads TAVILY_API_KEY from the environment automatically.
"""

from typing import Optional

from langchain_community.utilities.tavily_search import TavilySearchAPIWrapper

_wrapper: Optional[TavilySearchAPIWrapper] = None


def _get_wrapper() -> TavilySearchAPIWrapper:
    global _wrapper
    if _wrapper is None:
        _wrapper = TavilySearchAPIWrapper()
    return _wrapper


def search(query: str, max_results: int = 5, include_images: bool = True) -> dict:
    """
    Run a Tavily web search and return results + images.

    Uses TavilySearchAPIWrapper.raw_results() to get the full response,
    including the images list when include_images=True.

    Returns:
        {"results": [{"title": ..., "url": ..., "content": ...}],
         "images":  ["https://...", ...]}
    """
    raw = _get_wrapper().raw_results(
        query,
        max_results=max_results,
        include_images=include_images,
    )
    results = raw.get("results", [])
    images = [
        img for img in raw.get("images", [])
        if isinstance(img, str) and img.startswith("https")
    ]
    return {"results": results, "images": images}
