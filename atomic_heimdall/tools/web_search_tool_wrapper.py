# heimdall_atomic/tools/web_search_tool_wrapper.py

import sys
from typing import Optional
from rich.console import Console # Import Console for potential use by the wrapped agent

from atomic_agents.lib.base.base_tool import BaseTool
from schemas.tool_schemas import WebSearchToolInputSchema, WebSearchToolOutputSchema, WebSearchToolConfig

# --- Import the user's web search agent flow ---
# This assumes web_search_agent.py is in the same directory or accessible via PYTHONPATH
try:
    # Important: Ensure this import path matches your project structure
    from .web_search_agent import run_web_search_flow
except ImportError as e:
    print(f"CRITICAL Error importing 'run_web_search_flow' from 'web_search_agent': {e}", file=sys.stderr)
    print("Please ensure 'web_search_agent.py' and its dependencies exist in the 'tools' directory.", file=sys.stderr)
    # Define a dummy function to allow the script to load, but fail at runtime
    def run_web_search_flow(user_query: str, console: Optional[Console]) -> Optional[str]:
        raise ImportError("Web search agent flow could not be imported.") from e
    # Alternatively, exit here:
    # sys.exit(1)


class WebSearchToolWrapper(BaseTool):
    """
    Atomic Agents Tool: Wraps the user's existing multi-agent web search flow.
    Takes a user query and returns the final synthesized answer.
    """
    input_schema = WebSearchToolInputSchema
    output_schema = WebSearchToolOutputSchema

    def __init__(self, config: WebSearchToolConfig = WebSearchToolConfig()):
        super().__init__(config)
        # Initialize Rich Console for potential use by the wrapped flow
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
        user_query = params.user_query
        final_answer = None
        success = False

        print(f"WebSearchToolWrapper: Starting web search flow for query: '{user_query}'", file=sys.stderr)

        try:
            # Call the imported function from the user's web_search_agent.py
            # Pass the console object in case the original script uses it for printing
            result_markdown = run_web_search_flow(user_query=user_query, console=self.console)

            if result_markdown is not None:
                 # The run_web_search_flow returns a Markdown object or None.
                 # We need the string content for our schema.
                final_answer = str(result_markdown.markup) # Extract the string content
                success = True
                print("WebSearchToolWrapper: Web search flow completed successfully.", file=sys.stderr)
            else:
                print("WebSearchToolWrapper: Web search flow returned None (likely an internal error or no answer).", file=sys.stderr)
                final_answer = "The web search process completed, but no answer could be synthesized (check logs for details)."
                success = False # Indicate that while the process ran, it didn't yield a usable answer

        except ImportError as e:
             # Catch the specific import error if the dummy function was used
             print(f"WebSearchToolWrapper: CRITICAL ERROR - Could not execute web search. {e}", file=sys.stderr)
             final_answer = "Error: The web search tool is not configured correctly (failed to import agent flow)."
             success = False
        except Exception as e:
            print(f"WebSearchToolWrapper: Error during web search flow execution: {e}", file=sys.stderr)
            final_answer = f"An error occurred during the web search: {e}"
            success = False

        return WebSearchToolOutputSchema(final_answer=final_answer, success=success)

# Example usage (for testing the tool directly)
if __name__ == "__main__":
    # Ensure you have a .env file with GEMINI_API_KEY (or other key used by web_search_agent.py)
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

