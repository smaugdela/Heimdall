# heimdall_atomic/schemas/agent_schemas.py

from typing import Optional, Dict, Any
from pydantic import Field
from atomic_agents.lib.base.base_io_schema import BaseIOSchema

# --- Heimdall Agent Schemas ---

class HeimdallInputSchema(BaseIOSchema):
    """Input schema for the Heimdall agent, representing the user's request or task."""
    task: str = Field(..., description="The user's high-level pentesting task or question.")
    previous_tool_result: Optional[str] = Field(default=None, description="The result from the previously executed tool, if any.")

class HeimdallOutputSchema(BaseIOSchema):
    """
    Output schema for the Heimdall agent. It indicates the next step,
    which could be asking the user, using a tool, or providing a final response.
    """
    thought: str = Field(..., description="The agent's reasoning process and plan for the next step.")
    tool_to_use: Optional[str] = Field(default=None, description="The name of the tool to use next (e.g., 'HumanInTheLoopConsole', 'FileManager', 'WebSearchTool').", examples=["HumanInTheLoopConsole", "FileManager", "WebSearchTool", None])
    tool_parameters: Optional[Dict[str, Any]] = Field(default=None, description="The parameters required for the selected tool, matching the tool's input schema.")
    response_to_user: Optional[str] = Field(default=None, description="A direct message or final answer to the user if no tool is being used.")

