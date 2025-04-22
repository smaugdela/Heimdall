# heimdall_atomic/main.py

import os
import sys
import json
import instructor
import openai # Used for client setup even with Gemini/Ollama etc.
from dotenv import load_dotenv, find_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.markdown import Markdown

from atomic_agents.lib.components.agent_memory import AgentMemory

# Import agent and schemas
from heimdall_agent import HeimdallAgent
from schemas.agent_schemas import HeimdallInputSchema, HeimdallOutputSchema

# Import tools and their configs/schemas
from tools.human_in_the_loop_console_tool import HumanInTheLoopConsoleTool, ConsoleToolConfig, ConsoleToolInputSchema
from tools.file_manager_tool import FileManagerTool, FileManagerConfig, FileManagerInputSchema
from tools.web_search_tool_wrapper import WebSearchToolWrapper, WebSearchToolConfig, WebSearchToolInputSchema

# --- Configuration ---
# Load environment variables (.env file recommended for API keys)
load_dotenv(find_dotenv())

# Choose your LLM Provider and Model
# Ensure the corresponding API key is in your .env file
# Supported providers: 'openai', 'anthropic', 'groq', 'ollama', 'gemini'
PROVIDER = "gemini" # Change this to your desired provider
# PROVIDER = "openai"
# PROVIDER = "ollama"

# --- Client Setup ---
def setup_client(provider):
    """Sets up the Instructor client based on the chosen provider."""
    client = None
    model = None
    try:
        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key: raise ValueError("OPENAI_API_KEY not found in environment.")
            client = instructor.from_openai(openai.OpenAI(api_key=api_key))
            model = "gpt-4o-mini" # Or "gpt-4-turbo", "gpt-3.5-turbo"

        elif provider == "ollama":
            # Assumes Ollama server running at localhost:11434
            # Check model availability in your Ollama instance
            client = instructor.from_openai(
                openai.OpenAI(base_url="http://localhost:11434/v1", api_key="ollama"),
                mode=instructor.Mode.JSON # Use JSON mode for structured output
            )
            model = "llama3" # Or "mistral", "qwen", etc. - Ensure it supports JSON mode well

        elif provider == "gemini":
            # Uses OpenAI compatible endpoint
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key: raise ValueError("GEMINI_API_KEY not found in environment.")
            client = instructor.from_openai(
                openai.OpenAI(
                    api_key=api_key,
                    base_url="https://generativelanguage.googleapis.com/v1beta/models/" # Correct base URL for Gemini API
                ),
                mode=instructor.Mode.JSON # Use JSON mode
            )
            # Note: Gemini model names often need 'models/' prefix for the compatible endpoint
            model = "gemini-1.5-flash-latest" # Or "gemini-pro", check Gemini docs for JSON mode compatibility

        else:
            raise ValueError(f"Unsupported provider: {provider}")

        print(f"Using provider: {provider}, model: {model}", file=sys.stderr)
        return client, model

    except ImportError as e:
        print(f"Error: Missing library for provider '{provider}'. Please install it. {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: Configuration error for provider '{provider}'. {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error setting up client for provider '{provider}': {e}", file=sys.stderr)
        sys.exit(1)


# --- Main Execution Logic ---
def main():
    console = Console()
    console.print(Panel("[bold green]Welcome to Heimdall - Atomic Pentesting Assistant[/bold green]"))

    # --- Initialize Client and Agent ---
    client, model = setup_client(PROVIDER)
    shared_memory = AgentMemory() # Use shared memory for the entire session
    heimdall_agent = HeimdallAgent(client=client, model=model, memory=shared_memory)

    # --- Initialize Tools ---
    # Ensure the working directory exists
    fm_working_dir = "heimdall_workspace"
    if not os.path.exists(fm_working_dir):
        os.makedirs(fm_working_dir)

    tools = {
        "HumanInTheLoopConsole": HumanInTheLoopConsoleTool(ConsoleToolConfig()),
        "FileManager": FileManagerTool(FileManagerConfig(working_dir=fm_working_dir)),
        "WebSearchTool": WebSearchToolWrapper(WebSearchToolConfig())
    }
    console.print(f"[cyan]Initialized Tools:[/cyan] {', '.join(tools.keys())}")
    console.print(f"[cyan]FileManager working directory:[/cyan] {os.path.abspath(fm_working_dir)}")


    # --- Interaction Loop ---
    last_tool_result = None
    while True:
        try:
            user_input = console.input("\n👤 [bold green]You:[/bold green] ")
            if user_input.lower() in ["exit", "quit"]:
                console.print("[yellow]Exiting Heimdall Agent. Goodbye![/yellow]")
                break
            if not user_input.strip():
                continue

            # Add user message to memory
            heimdall_agent.memory.add_user_message(user_input)

            # Prepare input for the agent
            agent_input = HeimdallInputSchema(
                task=user_input,
                previous_tool_result=last_tool_result # Provide result from the *last* turn
            )
            last_tool_result = None # Reset last tool result after passing it

            console.print("\n🤖 [bold blue]Heimdall thinking...[/bold blue]", style="dim")

            # --- Run the Heimdall Agent ---
            try:
                agent_output: HeimdallOutputSchema = heimdall_agent.run(agent_input)
            except Exception as e:
                 console.print(f"[bold red]Error running Heimdall agent:[/bold red] {e}")
                 console.print("[red]Check model compatibility with JSON mode and API key validity.[/red]")
                 # Optionally add error to memory or just continue
                 heimdall_agent.memory.add_assistant_message(f"Internal Error: Could not process the request due to: {e}")
                 continue # Skip to next user input

            # --- Process Agent Output ---
            console.print(Panel(f"[dim]Thought:[/dim] {agent_output.thought}", title="Agent Thought", border_style="dim cyan"))

            # Check if a tool needs to be used
            if agent_output.tool_to_use:
                tool_name = agent_output.tool_to_use
                tool_params_dict = agent_output.tool_parameters

                if tool_name in tools:
                    tool_instance = tools[tool_name]
                    console.print(f"\n🛠️ [bold yellow]Using Tool:[/bold yellow] {tool_name}")
                    if tool_params_dict:
                         console.print(Syntax(json.dumps(tool_params_dict, indent=2), "json", theme="default", line_numbers=False, word_wrap=True))

                    try:
                        # Validate and create tool input schema instance
                        # This relies on Pydantic parsing the dict into the correct schema
                        tool_input_schema_class = tool_instance.input_schema
                        tool_input = tool_input_schema_class(**tool_params_dict)

                        # --- Run the Selected Tool ---
                        tool_output = tool_instance.run(tool_input)
                        # --- End Tool Run ---

                        console.print(f"\n✅ [bold green]Tool Result ({tool_name}):[/bold green]")
                        # Display tool output nicely (might be long)
                        result_str = tool_output.model_dump_json(indent=2)
                        console.print(Syntax(result_str, "json", theme="default", line_numbers=False, word_wrap=True))

                        # Store the raw result string for the next agent turn
                        last_tool_result = result_str

                        # Add tool result message to memory for the agent's context
                        # Use a specific role or format if needed
                        heimdall_agent.memory.add_message(
                            role="tool_result", # Custom role
                            message=f"Tool '{tool_name}' output:\n{result_str}"
                        )

                    except Exception as e:
                        console.print(f"[bold red]Error running tool '{tool_name}':[/bold red] {e}")
                        last_tool_result = f"Error running tool '{tool_name}': {e}"
                        heimdall_agent.memory.add_message(role="system", message=f"Error executing tool {tool_name}: {e}")

                else:
                    console.print(f"[bold red]Error:[/bold red] Agent specified unknown tool '{tool_name}'.")
                    last_tool_result = f"Error: Unknown tool '{tool_name}' requested."
                    heimdall_agent.memory.add_message(role="system", message=f"Agent hallucinated unknown tool: {tool_name}")


            # Check if the agent provided a direct response
            elif agent_output.response_to_user:
                console.print("\n🤖 [bold blue]Heimdall:[/bold blue]")
                console.print(Markdown(agent_output.response_to_user))
                # Add agent's direct response to memory
                heimdall_agent.memory.add_assistant_message(agent_output.response_to_user)
                last_tool_result = None # No tool was used

            else:
                # Agent didn't specify a tool or a response - might be an issue
                console.print("[bold yellow]Warning:[/bold yellow] Agent did not specify a tool or a response.")
                heimdall_agent.memory.add_assistant_message("Internal Note: No specific action taken in this turn.")
                last_tool_result = "Agent provided no actionable output."


        except KeyboardInterrupt:
            console.print("\n[yellow]Operation interrupted by user. Exiting.[/yellow]")
            break
        except EOFError:
            console.print("\n[yellow]Input stream closed. Exiting.[/yellow]")
            break
        except Exception as e:
            console.print(f"\n[bold red]An unexpected error occurred in the main loop:[/bold red] {e}")
            # Log the error, maybe attempt to recover or just break
            import traceback
            traceback.print_exc()
            # break # Optional: exit on unexpected errors

if __name__ == "__main__":
    main()
