# heimdall_agent/main.py

import os
import sys
import dotenv
from smolagents import CodeAgent # Main agent class
from smolagents.prompts import Persona # To load the persona
# Import the tool classes
from tools.human_in_the_loop_console import HumanInTheLoopConsole
from tools.file_manager import FileManager
from tools.web_search import WebSearch # This uses the external google_search

# --- Configuration ---
PERSONA_FILE = "persona.py"
# Define the working directory for the FileManager tool
# It's recommended to use a dedicated directory
WORKING_DIRECTORY = "heimdall_workspace"
# Set the Hugging Face model to use (example, choose a suitable one)
# Make sure you have access to this model (e.g., via API key if needed)
# Or use a locally hosted model if preferred.
# MODEL_NAME = "mistralai/Mistral-7B-Instruct-v0.1"
# MODEL_NAME = "meta-llama/Llama-2-7b-chat-hf"
# MODEL_NAME = "gpt-4" # Or gpt-3.5-turbo, claude-3-opus-20240229 etc. depending on availability

MODEL_NAME = "google/gemini-2.0-flash-thinking-exp-01-21"
GOOGLE_API_KEY = dotenv.get_key(dotenv.find_dotenv(), "GOOGLE_API_KEY")

# --- Initialization ---

def main():
    """Initializes and runs the Heimdall agent."""
    print("Initializing Heimdall Agent...")

    # 1. Load the Persona
    try:
        persona = Persona(PERSONA_FILE)
        print(f"Loaded persona from {PERSONA_FILE}")
    except FileNotFoundError:
        print(f"Error: Persona file '{PERSONA_FILE}' not found.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error loading persona: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. Initialize Tools
    # Ensure the working directory exists for the FileManager
    if not os.path.exists(WORKING_DIRECTORY):
        try:
            os.makedirs(WORKING_DIRECTORY)
            print(f"Created working directory: {WORKING_DIRECTORY}")
        except OSError as e:
            print(f"Error creating working directory '{WORKING_DIRECTORY}': {e}", file=sys.stderr)
            sys.exit(1)

    tools = [
        HumanInTheLoopConsole(),
        FileManager(working_dir=WORKING_DIRECTORY),
        WebSearch(), # Relies on the external google_search tool being available
    ]
    print(f"Initialized tools: {[tool.name for tool in tools]}")
    print(f"FileManager operating in: {os.path.abspath(WORKING_DIRECTORY)}")

    # 3. Initialize the Agent
    # Ensure you have set necessary environment variables if required by smol-agents
    # (e.g., OPENAI_API_KEY, HUGGINGFACE_API_KEY)
    try:
        agent = CodeAgent(
            persona=persona,
            tools=tools,
            model_name=MODEL_NAME, # Specify the model if needed
            # Add other agent configurations as required by smol-agents
            # e.g., max_steps, temperature, etc.
        )
        print(f"Agent initialized successfully using model: {agent.llm.model_name}") # Accessing the model name might vary
    except Exception as e:
        print(f"Error initializing Agent: {e}", file=sys.stderr)
        print("Please ensure the smol-agents library is installed correctly and any necessary API keys (e.g., OPENAI_API_KEY) are set.", file=sys.stderr)
        sys.exit(1)


    # 4. Start the interactive loop
    print("\n--- Heimdall Agent Ready ---")
    print("Enter your pentesting requests or tasks. Type 'exit' or 'quit' to end.")

    while True:
        try:
            user_input = input("\n👤 You: ")
            if user_input.lower().strip() in ["exit", "quit"]:
                print("Exiting Heimdall Agent. Goodbye!")
                break
            if not user_input.strip():
                continue

            # Let the agent process the input
            print("🤖 Heimdall is thinking...", file=sys.stderr)
            response = agent.step(user_input) # Or agent.run(user_input) depending on smol-agents version/usage

            # Print the agent's response (which might include tool calls handled internally)
            # The actual output format might depend on how smol-agents handles responses
            # This assumes response is a string or can be converted to one.
            print(f"\n🤖 Heimdall: {response}")

        except KeyboardInterrupt:
            print("\nCaught KeyboardInterrupt. Exiting Heimdall Agent.")
            break
        except EOFError:
             print("\nInput stream closed. Exiting Heimdall Agent.")
             break
        except Exception as e:
            # Catch potential errors during agent execution
            print(f"\nAn error occurred: {e}", file=sys.stderr)
            print("Please check the error message and your input.", file=sys.stderr)
            # Depending on the error, you might want to break or continue
            # continue

if __name__ == "__main__":
    main()
