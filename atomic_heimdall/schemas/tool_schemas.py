# heimdall_atomic/schemas/tool_schemas.py

import os
from typing import List, Optional
from pydantic import Field
from atomic_agents.lib.base.base_io_schema import BaseIOSchema
from atomic_agents.lib.base.base_tool import BaseToolConfig

# --- HumanInTheLoopConsole Schemas ---

class ConsoleToolInputSchema(BaseIOSchema):
    """Input schema for the HumanInTheLoopConsole tool."""
    command: str = Field(..., description="The exact shell command to propose for execution.")
    reason: str = Field(..., description="A brief explanation why this command should be run.")

class ConsoleToolOutputSchema(BaseIOSchema):
    """Output schema for the HumanInTheLoopConsole tool."""
    result: str = Field(..., description="The captured stdout/stderr from the executed command, or a message indicating rejection or error.")
    executed: bool = Field(..., description="Indicates whether the command was actually executed.")

class ConsoleToolConfig(BaseToolConfig):
    """Configuration for the Console Tool (if any needed in the future)."""
    timeout: int = Field(default=300, description="Timeout in seconds for command execution.")

# --- FileManager Schemas ---

class FileManagerInputSchema(BaseIOSchema):
    """Input schema for the FileManager tool."""
    action: str = Field(..., description="The file operation to perform.", examples=["read", "write", "append", "list"])
    path: str = Field(..., description="The relative path to the file or directory within the working directory.")
    content: Optional[str] = Field(default=None, description="The content to write or append (required for 'write'/'append').")
    reason: str = Field(..., description="A brief explanation why this file operation is needed (especially for write/append).")

class FileManagerOutputSchema(BaseIOSchema):
    """Output schema for the FileManager tool."""
    status: str = Field(..., description="A message indicating success or failure of the operation.")
    content: Optional[str] = Field(default=None, description="The content read from the file (for 'read' action) or a list of files (for 'list' action).")
    action_performed: bool = Field(..., description="Indicates if the requested action was successfully performed (including user approval).")

class FileManagerConfig(BaseToolConfig):
    """Configuration for the FileManager Tool."""
    working_dir: str = Field(default="heimdall_workspace", description="The base directory for all file operations.")

# --- WebSearchToolWrapper Schemas ---

class WebSearchToolInputSchema(BaseIOSchema):
    """Input schema for the WebSearchTool wrapper."""
    query: str = Field(..., description="The natural language query to search the web for.")

class WebSearchToolOutputSchema(BaseIOSchema):
    """
    Output schema for the WebSearchTool wrapper.
    Contains the final synthesized answer from the underlying web search agent.
    """
    final_answer: Optional[str] = Field(..., description="The synthesized answer from the web search agent, or None if an error occurred.")
    success: bool = Field(..., description="Indicates if the web search flow completed successfully.")

class WebSearchToolConfig(BaseToolConfig):
    """Configuration for the Web Search Tool Wrapper (if any needed)."""
    pass # No specific config needed for the wrapper itself for now
