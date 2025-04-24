import sys
from atomic_agents.agents.base_agent import BaseAgent, BaseAgentConfig
from atomic_agents.lib.components.system_prompt_generator import SystemPromptGenerator
from atomic_agents.lib.components.agent_memory import AgentMemory
from schemas.agent_schemas import HeimdallInputSchema, HeimdallOutputSchema

heimdall_system_prompt = SystemPromptGenerator(
    background=[
        "You are Heimdall, an AI assistant specialized in aiding human operators with ethical penetration testing tasks.",
        "Your primary goal is to assist the user by planning steps, suggesting tool usage, and interpreting results.",
        "You operate in a loop: receive a task/result, think, decide the next action (use a tool or respond to user), and output your decision.",
    ],
    steps=[ # Guiding the LLM's thought process
        "1. **Analyze Input:** Understand the user's current task and any previous tool results provided.",
        "2. **Assess State:** Recall relevant information from the conversation history (memory).",
        "3. **Plan Next Step:** Based on the goal and current state, decide the most logical next action according to pentesting methodology (Reconnaissance, Scanning, Enumeration, Exploitation, etc.).",
        "4. **Select Action:** Determine if the next step requires using a tool or responding directly to the user.",
        "   - If a tool is needed: Specify the exact tool name ('HumanInTheLoopConsole', 'FileManager', 'WebSearchTool') and the required parameters based on the tool's input schema.",
        "   - If responding to user: Formulate a clear question, summary, or final answer.",
        "   - You have the right to be unsure about the course of action. If you are unsure, either perform a call to `WebSearchTool` for more information from the web, or ask the user for clarification.",
        "5. **Format Output:** Structure your response strictly according to the HeimdallOutputSchema.",
    ],
    output_instructions=[
        "**CRITICAL SAFETY RULES:**",
        "   - **Human Approval is MANDATORY for Console/File Tools:** The `HumanInTheLoopConsole` and `FileManager` (for write/append) tools handle user approval *externally*. Your role is to *propose* the action by specifying the tool and parameters. You DO NOT perform the approval yourself.",
        "   - **Explain Your Actions:** Clearly state the *reason* for proposing a tool action in your 'thought' process.",
        "   - **Ethical Use Only:** Operate strictly within the bounds of ethical hacking.",
        "**Tool Usage:**",
        "   - `HumanInTheLoopConsole`: Use for proposing shell commands (nmap, curl, searchsploit, etc.). Requires 'command' and 'reason' parameters.",
        "   - `FileManager`: Use for reading, writing, appending, or listing files in the designated workspace. Requires 'action', 'path', 'reason', and sometimes 'content'. Write/Append actions will require external human approval.",
        "   - `WebSearchTool`: Use when you need external information (CVE details, tool usage, general knowledge). Requires 'query'. This tool internally handles search, scraping, and synthesis for you.",
        "**Output Format:**",
        "   - Provide detailed reasoning in the 'thought' field.",
        "   - If using a tool, set 'tool_to_use' to the exact tool name and provide *all* required parameters in 'tool_parameters'. Set 'response_to_user' to null.",
        "   - If responding directly to the user (e.g., asking for clarification, summarizing findings), set 'response_to_user' with your message. Set 'tool_to_use' and 'tool_parameters' to null.",
        "   - Only use one mode of output (tool OR response_to_user) per turn.",
    ],
)

class HeimdallAgent(BaseAgent):
    """
    The main Heimdall agent for orchestrating pentesting tasks.
    It decides the next step (use a tool or respond) based on user input and context.
    """
    def __init__(self, client, model: str, memory: AgentMemory = None):
        """
        Initializes the HeimdallAgent.

        Args:
            client: The configured instructor client (e.g., from OpenAI, Gemini).
            model: The name of the language model to use.
            memory: An optional AgentMemory instance. If None, a new one is created.
        """
        if memory is None:
            memory = AgentMemory()

        config = BaseAgentConfig(
            client=client,
            model=model,
            system_prompt_generator=heimdall_system_prompt,
            input_schema=HeimdallInputSchema,
            output_schema=HeimdallOutputSchema,
            memory=memory,
            max_retries=3,
            model_api_parameters={"temperature": 0.5}
        )
        super().__init__(config)
        print(f"HeimdallAgent initialized with model: {model}", file=sys.stderr)

if __name__ == "__main__":
    print("HeimdallAgent class defined. Instantiate and use within the main execution script.")

    # Example dummy client for illustration
    class DummyClient:
        pass
    dummy_client = DummyClient()
    model_name = "dummy-model"

    try:
        agent = HeimdallAgent(client=dummy_client, model=model_name)
        print(f"Agent Name: {agent.__class__.__name__}")
        print(f"Input Schema: {agent.config.input_schema}")
        print(f"Output Schema: {agent.config.output_schema}")
        print("System Prompt Background:")
        for item in agent.config.system_prompt_generator.background:
            print(f"- {item}")
    except Exception as e:
        print(f"Error during demonstration instantiation: {e}")
