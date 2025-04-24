import subprocess
import shlex
import sys
from atomic_agents.lib.base.base_tool import BaseTool
from schemas.tool_schemas import ConsoleToolInputSchema, ConsoleToolOutputSchema, ConsoleToolConfig

class HumanInTheLoopConsoleTool(BaseTool):
    """
    Atomic Agents Tool: Executes shell commands after explicit human approval.
    """
    input_schema = ConsoleToolInputSchema
    output_schema = ConsoleToolOutputSchema

    def __init__(self, config: ConsoleToolConfig = ConsoleToolConfig()):
        super().__init__(config)
        self.timeout = config.timeout

    def run(self, params: ConsoleToolInputSchema) -> ConsoleToolOutputSchema:
        """
        Proposes the command to the user and executes it if approved.
        You may use sudo for commands that require elevated privileges.

        Args:
            params: Input parameters including the command and reason.

        Returns:
            Output schema containing the result and execution status.
        """
        command = params.command
        reason = params.reason

        print("-" * 50, file=sys.stderr)
        print(f"🤖 Agent proposes running command:", file=sys.stderr)
        print(f"   Reason: {reason}", file=sys.stderr)
        print(f"   Command: `{command}`", file=sys.stderr)
        print("-" * 50, file=sys.stderr)

        executed = False
        output_result = "Command proposal initiated."

        while True:
            try:
                # Prompt the user for approval
                approval = input("Do you want to execute this command? (y/n/edit): ").lower().strip()
                if approval == 'y':
                    print("Executing command...", file=sys.stderr)
                    try:
                        # shlex for command parsing
                        process = subprocess.run(
                            shlex.split(command),
                            capture_output=True,
                            text=True,
                            check=False, # No exception raised
                            timeout=self.timeout
                        )

                        output = f"Exit Code: {process.returncode}\n"
                        if process.stdout:
                            output += f"--- STDOUT ---\n{process.stdout}\n"
                        if process.stderr:
                            output += f"--- STDERR ---\n{process.stderr}\n"

                        output_result = output.strip()
                        executed = True
                        print("Command execution finished.", file=sys.stderr)
                        break

                    except subprocess.TimeoutExpired:
                        print(f"Error: Command timed out after {self.timeout} seconds.", file=sys.stderr)
                        output_result = f"Error: Command execution timed out after {self.timeout} seconds."
                        executed = False
                        break
                    except FileNotFoundError:
                        cmd_name = shlex.split(command)[0] if shlex.split(command) else "Unknown"
                        print(f"Error: Command not found: {cmd_name}", file=sys.stderr)
                        output_result = f"Error: Command not found. Make sure '{cmd_name}' is installed and in PATH."
                        executed = False
                        break
                    except Exception as e:
                        print(f"Error executing command: {e}", file=sys.stderr)
                        output_result = f"Error executing command: {e}"
                        executed = False
                        break

                elif approval == 'n':
                    reason = input("Please provide a reason for rejection (or press Enter to skip): ").strip()
                    if not reason:
                        reason = "No reason provided."
                    output_result = "User rejected the command execution. Reason: " + reason
                    print(f"Command rejected by user. Reason: {reason}", file=sys.stderr)
                    executed = False
                    break

                elif approval == 'edit':
                    print("Please enter the new command (or press Enter to cancel):", file=sys.stderr)
                    new_command = input(">> ")
                    if new_command.strip():
                        command = new_command
                        print(f"Updated command: `{command}`", file=sys.stderr)
                        continue
                    else:
                        print("Edit cancelled. Command rejected.", file=sys.stderr)
                        output_result = "User cancelled edit and rejected the command execution."
                        executed = False
                        break
                else:
                    print("Invalid input. Please enter 'y', 'n', or 'edit'.", file=sys.stderr)

            except (EOFError, KeyboardInterrupt):
                print("\nOperation interrupted/cancelled by user. Rejecting command.", file=sys.stderr)
                output_result = "User interrupted/cancelled the operation, command rejected."
                executed = False
                break

        return ConsoleToolOutputSchema(result=output_result, executed=executed)

# Example usage (for testing the tool directly)
if __name__ == "__main__":
    console_tool = HumanInTheLoopConsoleTool()

    result = console_tool.run(ConsoleToolInputSchema(command="echo 'Hello from Heimdall!'", reason="Testing echo command"))
    print("\nResult:\n", result.model_dump_json(indent=2))

    result = console_tool.run(ConsoleToolInputSchema(command="ls -lha", reason="Listing files in the current directory"))
    print("\nResult:\n", result.model_dump_json(indent=2))
