import os
import sys
from typing import Optional
from atomic_agents.lib.base.base_tool import BaseTool
from schemas.tool_schemas import FileManagerInputSchema, FileManagerOutputSchema, FileManagerConfig

class FileManagerTool(BaseTool):
    """
    Atomic Agents Tool: Manages files within a designated working directory.
    Requires human approval for write/append operations.
    """
    input_schema = FileManagerInputSchema
    output_schema = FileManagerOutputSchema

    def __init__(self, config: FileManagerConfig = FileManagerConfig()):
        super().__init__(config)
        self.working_dir = os.path.abspath(config.working_dir)
        if not os.path.exists(self.working_dir):
            try:
                os.makedirs(self.working_dir)
                print(f"Created working directory: {self.working_dir}", file=sys.stderr)
            except OSError as e:
                print(f"CRITICAL Error creating working directory {self.working_dir}: {e}", file=sys.stderr)
                raise

        print(f"FileManagerTool initialized. Operations restricted to: {self.working_dir}", file=sys.stderr)

    def _resolve_path(self, path: str) -> Optional[str]:
        """Resolves relative path safely within the working directory."""
        # Prevent absolute paths from being provided by the agent
        if os.path.isabs(path):
             print(f"Error: Absolute paths are not allowed: {path}", file=sys.stderr)
             return None

        abs_path = os.path.normpath(os.path.join(self.working_dir, path))

        # Security check: Ensure the resolved path is still within the working directory
        if not abs_path.startswith(self.working_dir):
            print(f"Error: Attempted access outside the working directory: {path} resolved to {abs_path}", file=sys.stderr)
            return None
        return abs_path

    def _confirm_write_action(self, action: str, path: str, reason: str, content: Optional[str] = None) -> bool:
        """Gets user confirmation for write/append actions."""
        print("-" * 50, file=sys.stderr)
        print(f"🤖 Agent proposes file action:", file=sys.stderr)
        print(f"   Action: {action.upper()}", file=sys.stderr)
        print(f"   Path (relative): {path}", file=sys.stderr)
        print(f"   Reason: {reason}", file=sys.stderr)
        if content is not None:
            preview = (content[:200] + '...') if len(content) > 200 else content
            print(f"   Content Preview:\n---\n{preview}\n---", file=sys.stderr)
        print("-" * 50, file=sys.stderr)

        while True:
            try:
                approval = input(f"Do you want to {action} this file? (y/n): ").lower().strip()
                if approval == 'y':
                    return True
                elif approval == 'n':
                    return False
                else:
                    print("Invalid input. Please enter 'y' or 'n'.", file=sys.stderr)
            except (EOFError, KeyboardInterrupt):
                 print("\nOperation interrupted/cancelled by user.", file=sys.stderr)
                 return False

    def run(self, params: FileManagerInputSchema) -> FileManagerOutputSchema:
        """Performs the requested file operation after validation and confirmation."""
        action = params.action
        path = params.path
        reason = params.reason
        content_to_write = params.content

        safe_abs_path = self._resolve_path(path)
        if not safe_abs_path:
            return FileManagerOutputSchema(
                status=f"Error: Invalid or disallowed path '{path}'. Operations confined to '{os.path.basename(self.working_dir)}'.",
                action_performed=False
            )

        output_status = "Operation initiated."
        output_content = None
        action_performed = False

        try:
            if action == "read":
                if not os.path.exists(safe_abs_path):
                    output_status = f"Error: File not found at '{path}'."
                elif not os.path.isfile(safe_abs_path):
                    output_status = f"Error: '{path}' is not a file."
                else:
                    with open(safe_abs_path, 'r', encoding='utf-8') as f:
                        output_content = f.read()
                    output_status = f"Successfully read content from '{path}'."
                    action_performed = True

            elif action == "list":
                target_path = safe_abs_path
                # If path is a file, list its parent directory
                if os.path.isfile(target_path):
                     target_path = os.path.dirname(target_path)

                if not os.path.exists(target_path) or not os.path.isdir(target_path):
                     output_status = f"Error: Directory not found or is not a directory at '{path}'."
                else:
                    entries = os.listdir(target_path)
                    # Get relative path for display
                    relative_display_path = os.path.relpath(target_path, self.working_dir)
                    output_content = "\n".join(entries)
                    output_status = f"Successfully listed contents of directory '{relative_display_path}'."
                    action_performed = True

            elif action == "write" or action == "append":
                if content_to_write is None:
                    output_status = f"Error: 'content' parameter is required for '{action}' action."
                else:
                    parent_dir = os.path.dirname(safe_abs_path)
                    if not os.path.exists(parent_dir):
                        try:
                            os.makedirs(parent_dir)
                        except OSError as e:
                           output_status = f"Error: Could not create directory '{os.path.dirname(path)}': {e}"
                           return FileManagerOutputSchema(status=output_status, action_performed=False) # Early exit
                    elif not os.path.isdir(parent_dir):
                        output_status = f"Error: Cannot create file, '{os.path.dirname(path)}' is not a directory."
                        return FileManagerOutputSchema(status=output_status, action_performed=False) # Early exit

                    if not self._confirm_write_action(action, path, reason, content_to_write):
                        output_status = f"User rejected the '{action}' operation on '{path}'."
                    else:
                        mode = 'w' if action == 'write' else 'a'
                        with open(safe_abs_path, mode, encoding='utf-8') as f:
                            f.write(content_to_write)
                        output_status = f"Successfully performed '{action}' on file '{path}'."
                        action_performed = True
            else:
                output_status = f"Error: Unknown action '{action}'. Valid actions are 'read', 'write', 'append', 'list'."

        except IOError as e:
            output_status = f"Error performing '{action}' on '{path}': {e}"
            action_performed = False
        except Exception as e:
            print(f"Unexpected error in FileManagerTool: {e}", file=sys.stderr)
            output_status = f"Unexpected error during file operation: {e}"
            action_performed = False

        return FileManagerOutputSchema(
            status=output_status,
            content=output_content,
            action_performed=action_performed
        )

# Example usage
if __name__ == "__main__":

    test_dir = "test_fm_workspace"
    if not os.path.exists(test_dir):
        os.makedirs(test_dir)
    with open(os.path.join(test_dir, "existing_file.txt"), "w") as f:
        f.write("Initial content.")

    fm_tool = FileManagerTool(config=FileManagerConfig(working_dir=test_dir))

    print("--- Testing List ---")
    result = fm_tool.run(FileManagerInputSchema(action="list", path=".", reason="List base directory"))
    print(result.model_dump_json(indent=2))

    print("\n--- Testing Write ---")
    result = fm_tool.run(FileManagerInputSchema(action="write", path="new_notes.txt", content="This is a test note.", reason="Creating a test note"))
    print(result.model_dump_json(indent=2))

    print("\n--- Testing Read ---")
    result = fm_tool.run(FileManagerInputSchema(action="read", path="new_notes.txt", reason="Reading the test note"))
    print(result.model_dump_json(indent=2))

    print("\n--- Testing Append ---")
    result = fm_tool.run(FileManagerInputSchema(action="append", path="new_notes.txt", content="\nAdding more info.", reason="Appending to the test note"))
    print(result.model_dump_json(indent=2))

    print("\n--- Testing Write Subdir ---")
    result = fm_tool.run(FileManagerInputSchema(action="write", path="subdir/another_note.txt", content="Note in subdir", reason="Create note in subdir"))
    print(result.model_dump_json(indent=2))

    print("\n--- Testing List Subdir ---")
    result = fm_tool.run(FileManagerInputSchema(action="list", path="subdir", reason="List subdir after creation"))
    print(result.model_dump_json(indent=2))

    # Test path traversal attempt (should fail)
    print("\n--- Testing Path Traversal ---")
    result = fm_tool.run(FileManagerInputSchema(action="read", path="../outside_file.txt", reason="Attempting path traversal"))
    print(result.model_dump_json(indent=2))

    # Test absolute path attempt (should fail)
    print("\n--- Testing Absolute Path ---")
    abs_path_test = os.path.abspath("some_other_file.txt")
    result = fm_tool.run(FileManagerInputSchema(action="read", path=abs_path_test, reason="Attempting absolute path"))
    print(result.model_dump_json(indent=2))

    # Clean up test workspace
    import shutil
    shutil.rmtree(test_dir)
