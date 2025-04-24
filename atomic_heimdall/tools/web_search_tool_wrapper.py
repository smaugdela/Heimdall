import sys
from rich.console import Console

from atomic_agents.lib.base.base_tool import BaseTool
from schemas.tool_schemas import WebSearchToolInputSchema, WebSearchToolOutputSchema, WebSearchToolConfig
from .web_search_agent import run_web_search_flow


class WebSearchToolWrapper(BaseTool):
    """
    Atomic Agents Tool: Wraps the user's existing multi-agent web search flow.
    Takes a user query and returns the final synthesized answer.
    """
    input_schema = WebSearchToolInputSchema
    output_schema = WebSearchToolOutputSchema

    def __init__(self, config: WebSearchToolConfig = WebSearchToolConfig()):
        super().__init__(config)
        self.console = Console()
        print("WebSearchToolWrapper initialized.", file=sys.stderr)

    def run(self, params: WebSearchToolInputSchema) -> WebSearchToolOutputSchema:
        """
        Executes the wrapped web search agent flow.

        Args:
            params: Input schema containing the user_query.

        Returns:
            Output schema containing the final_answer and success status.
        """
        user_query = params.query
        final_answer = None
        success = False

        print(f"WebSearchToolWrapper: Starting web search flow for query: '{user_query}'", file=sys.stderr)

        try:
            result_markdown = run_web_search_flow(user_query=user_query, console=self.console)

            if result_markdown is not None:
                final_answer = str(result_markdown.markup)
                success = True
                print("WebSearchToolWrapper: Web search flow completed successfully.", file=sys.stderr)
            else:
                print("WebSearchToolWrapper: Web search flow returned None (likely an internal error or no answer).", file=sys.stderr)
                final_answer = "The web search process completed, but no answer could be synthesized (check logs for details)."
                success = False

        except ImportError as e:
             print(f"WebSearchToolWrapper: CRITICAL ERROR - Could not execute web search. {e}", file=sys.stderr)
             final_answer = "Error: The web search tool is not configured correctly (failed to import agent flow)."
             success = False
        except Exception as e:
            print(f"WebSearchToolWrapper: Error during web search flow execution: {e}", file=sys.stderr)
            final_answer = f"An error occurred during the web search: {e}"
            success = False

        return WebSearchToolOutputSchema(final_answer=final_answer, success=success)

if __name__ == "__main__":
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv())

    web_search_tool = WebSearchToolWrapper()

    test_query = "What is CVE-2021-44228 (Log4Shell)?"
    print(f"\n--- Testing Web Search Wrapper with query: '{test_query}' ---")

    result = web_search_tool.run(WebSearchToolInputSchema(user_query=test_query))

    print("\n--- Web Search Wrapper Result ---")
    print(result.model_dump_json(indent=2))

    if result.success and result.final_answer:
        print("\n--- Final Answer ---")
        print(result.final_answer)
    else:
        print("\nWeb search did not complete successfully or returned no answer.")
