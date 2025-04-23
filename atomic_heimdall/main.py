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
from rich.table import Table

from atomic_agents.lib.components.agent_memory import AgentMemory
from atomic_agents.lib.base.base_tool import BaseTool, BaseIOSchema

# Import agent and schemas
from heimdall_agent import HeimdallAgent
from schemas.agent_schemas import HeimdallInputSchema, HeimdallOutputSchema, TextMessageSchema

# Import tools and their configs/schemas
from tools.human_in_the_loop_console_tool import HumanInTheLoopConsoleTool, ConsoleToolConfig
from tools.file_manager_tool import FileManagerTool, FileManagerConfig
from tools.web_search_tool_wrapper import WebSearchToolWrapper, WebSearchToolConfig

# --- Configuration ---
load_dotenv(find_dotenv())
PROVIDER = "gemini" # Change this as needed: "openai", "ollama", "mistral", etc.
MAX_AUTO_STEPS = 10 # Safety limit for consecutive tool calls without user interaction

# --- Client Setup ---
def setup_client(provider):
    """Sets up the Instructor client based on the chosen provider."""
    client = None
    model = None
    try:
        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key: raise ValueError("OPENAI_API_KEY not found.")
            client = instructor.from_openai(openai.OpenAI(api_key=api_key))
            model = "gpt-4o-mini"
        elif provider == "ollama":
            client = instructor.from_openai(
                openai.OpenAI(base_url="http://localhost:11434/v1", api_key="ollama"),
                mode=instructor.Mode.JSON
            )
            model = "llama3" # Ensure this model works well with JSON mode
        elif provider == "gemini":
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key: raise ValueError("GEMINI_API_KEY not found.")
            client = instructor.from_openai(
                openai.OpenAI(api_key=api_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/"),
                mode=instructor.Mode.JSON
            )
            # Use a model known to work well with function calling/JSON mode
            model = "gemini-2.0-flash"
        elif provider == "mistral":
            # Requires 'pip install mistralai'
            from mistralai.client import MistralClient
            api_key = os.getenv("MISTRAL_API_KEY")
            if not api_key: raise ValueError("MISTRAL_API_KEY not found.")
            # Use instructor's dedicated mistral client setup
            client = instructor.from_mistral(
                 MistralClient(api_key=api_key), mode=instructor.Mode.MISTRAL_TOOLS # Use TOOL mode for Mistral
            )
            # Use a model known to support tool calling well
            model = "mistral-large-latest" # Or "mistral-small-latest" if large is unavailable/costly

        # Add Anthropic/Groq if needed following their specific instructor setup
        # elif provider == "anthropic": ...
        # elif provider == "groq": ...

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

# --- Helper Function for Pretty Printing Tool Output ---
def display_tool_output(console: Console, tool_name: str, tool_output: BaseIOSchema):
    """Formats and prints tool output using Rich components."""
    panel_title = f"Tool Result ({tool_name})"
    try:
        output_dict = tool_output.model_dump()
        # Create a table for key-value pairs
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column(style="bold cyan", width=25) # Key column
        table.add_column(style="white") # Value column

        for key, value in output_dict.items():
            # Nicely format common types
            if isinstance(value, bool):
                value_str = f"[bold green]True[/bold green]" if value else f"[bold red]False[/bold red]"
            elif isinstance(value, (list, dict)):
                 # Use JSON syntax for complex types within the table cell
                 value_str = Syntax(json.dumps(value, indent=2), "json", theme="default", line_numbers=False, word_wrap=True)
            elif isinstance(value, str) and '\n' in value:
                 # Use Markdown for multi-line strings
                 value_str = Markdown(value, inline_code_theme="default")
            else:
                value_str = str(value)

            table.add_row(f"{key}:", value_str)

        console.print(Panel(table, title=panel_title, border_style="green", expand=False))

    except Exception as e:
        # Fallback if formatting fails
        console.print(Panel(f"[red]Error formatting output:[/red] {e}\n\n[dim]{tool_output.model_dump_json(indent=2)}[/dim]", title=panel_title, border_style="red"))


# --- Main Execution Logic ---
def main():
    console = Console()
    console.print(Panel("[bold green]Welcome to Heimdall - Atomic Pentesting Assistant[/bold green]", title_align="center"))

    # --- Initialize Client and Agent ---
    client, model = setup_client(PROVIDER)
    shared_memory = AgentMemory()
    heimdall_agent = HeimdallAgent(client=client, model=model, memory=shared_memory)
    console.print(f"[cyan]Heimdall Agent initialized with model:[/cyan] {model}")

    # --- Initialize Tools ---
    fm_working_dir = "heimdall_workspace"
    if not os.path.exists(fm_working_dir):
        os.makedirs(fm_working_dir)

    tools: dict[str, BaseTool] = {
        "HumanInTheLoopConsole": HumanInTheLoopConsoleTool(ConsoleToolConfig()),
        "FileManager": FileManagerTool(FileManagerConfig(working_dir=fm_working_dir)),
        "WebSearchTool": WebSearchToolWrapper(WebSearchToolConfig())
    }
    console.print(f"[cyan]Initialized Tools:[/cyan] {', '.join(tools.keys())}")
    console.print(f"[cyan]FileManager working directory:[/cyan] {os.path.abspath(fm_working_dir)}")

    # --- Outer Interaction Loop (Gets initial user input) ---
    while True:
        try:
            # --- Get User Input ---
            user_input_text = console.input("\n👤 [bold green]You:[/bold green] ")
            if user_input_text.lower() in ["exit", "quit"]:
                console.print("[yellow]Exiting Heimdall Agent. Goodbye![/yellow]")
                break
            if not user_input_text.strip():
                continue

            # --- Add User Message to Memory ---
            heimdall_agent.memory.add_message(
                role="user",
                content=TextMessageSchema(text=user_input_text)
            )

            # --- Inner Auto-Loop (Agent thinks and uses tools) ---
            current_task = user_input_text
            last_tool_result_str = None
            step_count = 0

            while step_count < MAX_AUTO_STEPS:
                step_count += 1
                console.print(f"\n🤖 [bold blue]Heimdall thinking (Step {step_count})...[/bold blue]", style="dim")

                # --- Prepare Agent Input for this step ---
                # Use the original task unless it's a subsequent step
                task_for_agent = current_task if step_count == 1 else "Continue with the plan based on the last tool result."
                agent_input = HeimdallInputSchema(
                    task=task_for_agent,
                    previous_tool_result=last_tool_result_str
                )
                last_tool_result_str = None # Reset for the next potential tool use

                # --- Run the Heimdall Agent ---
                try:
                    agent_output: HeimdallOutputSchema = heimdall_agent.run(agent_input)
                except Exception as e:
                    console.print(f"[bold red]Error running Heimdall agent:[/bold red] {e}")
                    console.print("[red]Check model compatibility, API key, and prompt instructions.[/red]")
                    heimdall_agent.memory.add_message(
                        role="system",
                        content=TextMessageSchema(text=f"Internal Error during agent run: {e}")
                    )
                    break # Exit inner loop on agent error

                # --- Process Agent Output ---
                console.print(Panel(f"[dim]Thought:[/dim] {agent_output.thought}", title=f"Agent Thought (Step {step_count})", border_style="dim cyan", title_align="left"))

                # --- Handle Tool Usage ---
                if agent_output.tool_to_use:
                    tool_name = agent_output.tool_to_use
                    tool_params_dict = agent_output.tool_parameters or {} # Ensure dict

                    if tool_name in tools:
                        tool_instance = tools[tool_name]
                        console.print(f"\n🛠️ [bold yellow]Using Tool:[/bold yellow] {tool_name}")
                        # Display parameters nicely before execution
                        if tool_params_dict:
                             param_table = Table(show_header=False, box=None, padding=(0, 1))
                             param_table.add_column(style="bold magenta")
                             param_table.add_column()
                             for k, v in tool_params_dict.items():
                                 param_table.add_row(f"{k}:", str(v))
                             console.print(Panel(param_table, title="Tool Parameters", border_style="magenta", expand=False))

                        try:
                            # --- Run the Selected Tool ---
                            tool_input_schema_class = tool_instance.input_schema
                            tool_input = tool_input_schema_class(**tool_params_dict)
                            tool_output = tool_instance.run(tool_input)

                            # --- Display Tool Result ---
                            display_tool_output(console, tool_name, tool_output)

                            # --- Update Memory and Prepare for Next Step ---
                            result_str = tool_output.model_dump_json()
                            last_tool_result_str = result_str # Store for next agent input
                            heimdall_agent.memory.add_message(
                                role="system",
                                content=TextMessageSchema(text=f"Tool '{tool_name}' output:\n{result_str}")
                            )
                            # Continue the inner loop
                            continue

                        except Exception as e:
                            console.print(f"[bold red]Error running tool '{tool_name}':[/bold red] {e}")
                            error_message = f"Error running tool '{tool_name}': {e}"
                            last_tool_result_str = error_message
                            heimdall_agent.memory.add_message(
                                role="system",
                                content=TextMessageSchema(text=error_message)
                            )
                            break # Exit inner loop on tool error
                    else:
                        # Handle unknown tool
                        console.print(f"[bold red]Error:[/bold red] Agent specified unknown tool '{tool_name}'.")
                        error_message = f"Error: Unknown tool '{tool_name}' requested."
                        last_tool_result_str = error_message
                        heimdall_agent.memory.add_message(
                            role="system",
                            content=TextMessageSchema(text=f"Agent hallucinated unknown tool: {tool_name}")
                        )
                        break # Exit inner loop

                # --- Handle Direct Agent Response ---
                elif agent_output.response_to_user:
                    response_text = agent_output.response_to_user
                    console.print("\n🤖 [bold blue]Heimdall:[/bold blue]")
                    console.print(Panel(Markdown(response_text), border_style="blue", title="Agent Response", title_align="left"))
                    heimdall_agent.memory.add_message(
                        role="assistant",
                        content=TextMessageSchema(text=response_text)
                    )
                    break # Exit inner loop, wait for next user input

                # --- Handle No Action ---
                else:
                    warning_text = "Warning: Agent did not specify a tool or a response. Ending current task."
                    console.print(f"[bold yellow]{warning_text}[/bold yellow]")
                    heimdall_agent.memory.add_message(
                        role="system",
                        content=TextMessageSchema(text="Internal Note: Agent provided no actionable output. Ending loop.")
                    )
                    break # Exit inner loop

            # --- End of Inner Auto-Loop ---
            if step_count >= MAX_AUTO_STEPS:
                console.print(f"[bold yellow]Warning:[/bold yellow] Reached maximum auto steps ({MAX_AUTO_STEPS}). Pausing for user input.")
                heimdall_agent.memory.add_message(
                    role="system",
                    content=TextMessageSchema(text=f"Reached max auto steps ({MAX_AUTO_STEPS}). Waiting for user.")
                )

        # --- Outer Loop Exception Handling ---
        except KeyboardInterrupt:
            console.print("\n[yellow]Operation interrupted by user. Exiting.[/yellow]")
            break
        except EOFError:
            console.print("\n[yellow]Input stream closed. Exiting.[/yellow]")
            break
        except Exception as e:
            console.print(f"\n[bold red]An unexpected error occurred in the main loop:[/bold red] {e}")
            import traceback
            traceback.print_exc()
            try:
                 heimdall_agent.memory.add_message(
                     role="system",
                     content=TextMessageSchema(text=f"FATAL ERROR in main loop: {e}\n{traceback.format_exc()}")
                 )
            except Exception as mem_err:
                 print(f"[red]Additionally failed to add fatal error to memory: {mem_err}[/red]")
            # break # Decide if you want to exit on unexpected errors

if __name__ == "__main__":
    main()
