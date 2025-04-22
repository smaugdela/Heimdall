from typing import List, Literal, Optional
from pydantic import Field
from tenacity import retry, stop_after_attempt, stop_after_delay, wait_exponential
from duckduckgo_search import DDGS

from atomic_agents.agents.base_agent import BaseIOSchema
from atomic_agents.lib.base.base_tool import BaseTool, BaseToolConfig

"""
This module provides a tool for performing searches on DuckDuckGo based on the provided queries.
Can perform text, image, and news searches.
Rate-limited to 20 requests per second (duckduckgo policy).
"""

################
# INPUT SCHEMA #
################
class DuckDuckGoSearchToolInputSchema(BaseIOSchema):
    """
    Schema for input to a tool for searching for information using DuckDuckGo.
    Returns a list of search results.
    """
    queries: List[str] = Field(..., description="List of search queries.")
    max_results: Optional[int] = Field(3, description="Maximum number of results to retrieve per query.")
    category: Optional[str] = Field("text", description="Type of search to perform (text, images, news).")


####################
# OUTPUT SCHEMA(S) #
####################
class DuckDuckGoSearchResultItemSchema(BaseIOSchema):
    """Base schema for a single search result item"""
    url: str = Field(..., description="The URL of the search result")
    title: str = Field(..., description="The title of the search result")
    query: str = Field(..., description="The query used to obtain this search result")


class DuckDuckGoImageResultItemSchema(DuckDuckGoSearchResultItemSchema):
    """Schema for a single image search result item"""
    image_url: str = Field(..., description="The URL of the image")
    thumbnail_url: Optional[str] = Field(None, description="The URL of the thumbnail image")
    width: Optional[int] = Field(None, description="Width of the image")
    height: Optional[int] = Field(None, description="Height of the image")


class DuckDuckGoNewsResultItemSchema(DuckDuckGoSearchResultItemSchema):
    """Schema for a single news search result item"""
    source: Optional[str] = Field(None, description="Source of the news article")
    date: Optional[str] = Field(None, description="Publication date of the article")


class DuckDuckGoSearchToolOutputSchema(BaseIOSchema):
    """Base schema for the output of the DuckDuckGo search tool."""
    results: List[DuckDuckGoSearchResultItemSchema] = Field(..., description="List of search result items")


class DuckDuckGoImageSearchToolOutputSchema(BaseIOSchema):
    """Schema for the output of the DuckDuckGo image search tool."""
    results: List[DuckDuckGoImageResultItemSchema] = Field(..., description="List of image search result items")


class DuckDuckGoNewsSearchToolOutputSchema(BaseIOSchema):
    """Schema for the output of the DuckDuckGo news search tool."""
    results: List[DuckDuckGoNewsResultItemSchema] = Field(..., description="List of news search result items")


##############
# TOOL LOGIC #
##############
class DuckDuckGoSearchToolConfig(BaseToolConfig):
    """
    Configuration for the DuckDuckGoSearchTool.
    Attributes:
        safesearch (str): The safe search level (on, moderate, off).
        region (Optional[str]): The region to focus the search on (e.g., 'us-en').
    """
    safesearch: Literal["on", "moderate", "off"] = Field(
        "off", description="Safe search level."
    )
    region: Optional[str] = Field("wt-wt", description="The region to focus the search on (e.g., 'us-en').")


class DuckDuckGoSearchTool(BaseTool):
    """
    Tool for performing searches on DuckDuckGo based on the provided queries.
    """
    input_schema = DuckDuckGoSearchToolInputSchema
    output_schema = DuckDuckGoSearchToolOutputSchema

    def __init__(self, config: DuckDuckGoSearchToolConfig = DuckDuckGoSearchToolConfig()):
        super().__init__(config)
        self.safesearch = config.safesearch
        self.region = config.region

    def _fetch_search_results(self, query: str, max_results: int, search_type: str) -> List[dict]:
        """
        Fetches search results for a single query using DuckDuckGoSearch.

        Args:
            query (str): The search query.
            max_results (int): The maximum number of results to retrieve.
            search_type (str): The type of search to perform ('text', 'images', 'videos', 'news').

        Returns:
            List[dict]: A list of search result dictionaries.
        """
        with DDGS() as ddgs:
            if search_type == "text":
                results = ddgs.text(query, safesearch=self.safesearch, region=self.region, max_results=max_results)
            elif search_type == "images":
                results = ddgs.images(query, safesearch=self.safesearch, region=self.region, max_results=max_results)
            elif search_type == "videos":
                results = ddgs.videos(query, safesearch=self.safesearch, region=self.region, max_results=max_results)
            elif search_type == "news":
                results = ddgs.news(query, safesearch=self.safesearch, region=self.region, max_results=max_results)
            else:
                raise ValueError(f"Invalid search type: {search_type}")

            # Add the query to each result
            for result in results:
                result["query"] = query
            return results

    @retry(
        stop=stop_after_attempt(10) | stop_after_delay(60),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def run(self, params: DuckDuckGoSearchToolInputSchema) -> DuckDuckGoSearchToolOutputSchema:
        """
        Runs the DuckDuckGoSearchTool with the given parameters.

        Args:
            params (DuckDuckGoSearchToolInputSchema): The input parameters for the tool.

        Returns:
            DuckDuckGoSearchToolOutputSchema: The output of the tool.
        """
        all_results = []

        for query in params.queries:
            results = self._fetch_search_results(
                query,
                params.max_results,
                params.category,
            )
            all_results.extend(results)

        # Deduplicate results based on URL while preserving order
        seen_urls = set()
        unique_results = []
        for result in all_results:
            if result.get("url") or result.get("href") not in seen_urls:
                unique_results.append(result)
                seen_urls.add(result.get("url") or result.get("href"))

        if params.category == "text":
            formatted_results = [
                DuckDuckGoSearchResultItemSchema(
                    url=result.get("url") or result.get("href"),
                    title=result["title"],
                    snippet=result.get("body"),
                    query=result["query"]
                )
                for result in unique_results
            ]
            return DuckDuckGoSearchToolOutputSchema(results=formatted_results)

        elif params.category == "images":
            formatted_results = [
                DuckDuckGoImageResultItemSchema(
                    url=result.get("url") or result.get("href"),
                    title=result["title"],
                    image_url=result["image"],
                    thumbnail_url=result.get("thumbnail"),
                    width=result.get("width"),
                    height=result.get("height"),
                    query=result["query"]
                )
                for result in unique_results
            ]
            return DuckDuckGoImageSearchToolOutputSchema(results=formatted_results)

        elif params.category == "news":
            formatted_results = [
                DuckDuckGoNewsResultItemSchema(
                    url=result.get("url") or result.get("href"),
                    title=result["title"],
                    source=result.get("source"),
                    date=result.get("date"),
                    query=result["query"]
                )
                for result in unique_results
            ]
            return DuckDuckGoNewsSearchToolOutputSchema(results=formatted_results)
        else:
            return DuckDuckGoSearchToolOutputSchema(results=[])


#################
# EXAMPLE USAGE #
#################
if __name__ == "__main__":
    from rich.console import Console

    rich_console = Console()

    # Example Usage for Text Search
    text_search_tool = DuckDuckGoSearchTool(
        DuckDuckGoSearchToolConfig(
            safesearch="moderate",
        )
    )
    text_search_input = DuckDuckGoSearchTool.input_schema(
        queries=["Python programming", "Machine learning", "Artificial intelligence"],
        max_results=3,
    )
    text_output = text_search_tool.run(text_search_input, search_type="text")
    rich_console.print("Text Search Results:")
    rich_console.print(text_output)

    # Example Usage for Image Search
    image_search_tool = DuckDuckGoSearchTool(
        DuckDuckGoSearchToolConfig(
            safesearch="moderate",
        )
    )
    image_search_input = DuckDuckGoSearchTool.input_schema(
        queries=["Cute cats", "Funny dogs"],
        max_results=3,
    )
    image_output = image_search_tool.run(image_search_input, search_type="images")
    rich_console.print("\nImage Search Results:")
    rich_console.print(image_output)

    # Example Usage for News Search
    news_search_tool = DuckDuckGoSearchTool(
        DuckDuckGoSearchToolConfig(
            safesearch="moderate",
        )
    )
    news_search_input = DuckDuckGoSearchTool.input_schema(
        queries=["Latest AI news", "Space exploration updates"],
        max_results=3,
    )
    news_output = news_search_tool.run(news_search_input, search_type="news")
    rich_console.print("\nNews Search Results:")
    rich_console.print(news_output)
