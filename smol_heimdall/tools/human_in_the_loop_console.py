# heimdall_agent/tools/human_in_the_loop_console.py

import subprocess
import shlex
import sys
from typing import Dict, Any

class HumanInTheLoopConsole:
    """
    A tool that allows the LLM agent to propose shell commands,
    which are then presented to the human user for approval before execution.
    """
    # Tool name (as seen by the LLM)
    name: str = "HumanInTheLoopConsole"
    # Description (for the LLM)
    description: str = (
        "Proposes a shell command for execution. "
        "IMPORTANT: The command will ONLY be executed after explicit human approval. "
        "Captures and returns the command's stdout and stderr."
    )
    # Input schema (for the LLM)
    input_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The exact shell command to propose for execution."
            },
            "reason": {
                "type": "string",
                "description": "A brief explanation why this command should be run."
            }
        },
        "required": ["command", "reason"]
    }

    def __call__(self, command: str, reason: str) -> str:
        """
        Proposes the command to the user and executes it if approved.

        Args:
            command: The shell command string proposed by the LLM.
            reason: The reason provided by the LLM for running the command.

        Returns:
            A string containing the result (stdout/stderr) or a message
            indicating the command was rejected or an error occurred.
        """
        print("-" * 50, file=sys.stderr)
        print(f"🤖 Agent proposes running command:", file=sys.stderr)
        print(f"   Reason: {reason}", file=sys.stderr)
        print(f"   Command: `{command}`", file=sys.stderr)
        print("-" * 50, file=sys.stderr)

        while True:
            try:
                # Prompt the user for approval
                approval = input("Do you want to execute this command? (y/n/edit): ").lower().strip()
                if approval == 'y':
                    print("Executing command...", file=sys.stderr)
                    try:
                        # Use shlex.split for safer command parsing, especially with quotes
                        # Run the command using subprocess
                        # Combine stdout and stderr for simplicity
                        process = subprocess.run(
                            shlex.split(command),
                            capture_output=True,
                            text=True,
                            check=False, # Don't raise exception on non-zero exit code
                            timeout=300 # Add a timeout (e.g., 5 minutes)
                        )
                        # Combine stdout and stderr
                        output = f"Exit Code: {process.returncode}\n"
                        if process.stdout:
                            output += f"--- STDOUT ---\n{process.stdout}\n"
                        if process.stderr:
                            output += f"--- STDERR ---\n{process.stderr}\n"

                        print("Command execution finished.", file=sys.stderr)
                        return output.strip()

                    except subprocess.TimeoutExpired:
                        print("Error: Command timed out.", file=sys.stderr)
                        return "Error: Command execution timed out after 300 seconds."
                    except FileNotFoundError:
                        print(f"Error: Command not found: {shlex.split(command)[0]}", file=sys.stderr)
                        return f"Error: Command not found. Make sure '{shlex.split(command)[0]}' is installed and in PATH."
                    except Exception as e:
                        print(f"Error executing command: {e}", file=sys.stderr)
                        return f"Error executing command: {e}"

                elif approval == 'n':
                    reason = input("Please provide a reason for rejecting the command: ").strip()
                    if not reason:
                        reason = "No reason provided."
                    print(f"Command rejected by user. Reason: {reason}", file=sys.stderr)
                    return "User rejected the command execution, reason: " + reason
                elif approval == 'edit':
                    print("Please enter the new command (or press Enter to cancel):", file=sys.stderr)
                    new_command = input("> ")
                    if new_command.strip():
                        command = new_command # Update command to the edited version
                        print(f"Updated command: `{command}`", file=sys.stderr)
                        # Loop back to ask for approval of the *new* command
                        continue
                    else:
                        print("Edit cancelled. Command rejected.", file=sys.stderr)
                        return "User cancelled edit and rejected the command execution."
                else:
                    print("Invalid input. Please enter 'y', 'n', or 'edit'.", file=sys.stderr)

            except EOFError:
                print("\nInput stream closed. Rejecting command.", file=sys.stderr)
                return "Error: Input stream closed, command rejected."
            except KeyboardInterrupt:
                print("\nOperation interrupted by user. Rejecting command.", file=sys.stderr)
                return "User interrupted the operation, command rejected."

# Example usage (for testing the tool directly)
if __name__ == "__main__":
    console_tool = HumanInTheLoopConsole()
    # Test 1: Simple command
    result = console_tool(command="echo 'Hello from Heimdall!'", reason="Testing echo command")
    print("\nResult:\n", result)
    # Test 2: Command likely to fail (if 'nonexistentcommand' isn't real)
    result = console_tool(command="nonexistentcommand -v", reason="Testing error handling")
    print("\nResult:\n", result)
    # Test 3: Listing files
    result = console_tool(command="ls -lha", reason="Listing files in the current directory")
    print("\nResult:\n", result)
