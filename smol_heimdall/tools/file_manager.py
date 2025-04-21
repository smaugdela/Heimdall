# heimdall_agent/tools/file_manager.py

import os
import sys
from typing import Dict, Any, Optional

class FileManager:
    """
    A tool for reading, writing, appending, and listing files.
    Write and append operations require explicit human approval.
    Operations are restricted to a specific working directory for safety.
    """
    name: str = "FileManager"
    description: str = (
        "Manages files within a designated working directory. "
        "Allows reading files ('read'), listing directory contents ('list'), "
        "writing to files ('write'), and appending to files ('append'). "
        "IMPORTANT: 'write' and 'append' actions require explicit human approval."
    )
    input_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read", "write", "append", "list"],
                "description": "The file operation to perform."
            },
            "path": {
                "type": "string",
                "description": "The relative path to the file or directory within the working directory."
            },
            "content": {
                "type": "string",
                "description": "The content to write or append (only required for 'write' and 'append' actions)."
            },
             "reason": {
                "type": "string",
                "description": "A brief explanation why this file operation is needed (especially important for write/append)."
            }
        },
        "required": ["action", "path", "reason"]
    }

    def __init__(self, working_dir: str = "heimdall_workspace"):
        """
        Initializes the FileManager, creating the working directory if it doesn't exist.

        Args:
            working_dir: The directory where all file operations will be contained.
        """
        self.working_dir = os.path.abspath(working_dir)
        if not os.path.exists(self.working_dir):
            try:
                os.makedirs(self.working_dir)
                print(f"Created working directory: {self.working_dir}", file=sys.stderr)
            except OSError as e:
                print(f"Error creating working directory {self.working_dir}: {e}", file=sys.stderr)
                raise # Re-raise the exception as this is critical

        print(f"FileManager initialized. Operations restricted to: {self.working_dir}", file=sys.stderr)

    def _resolve_path(self, path: str) -> Optional[str]:
        """
        Resolves the given relative path against the working directory
        and ensures it stays within the working directory.

        Args:
            path: The relative path provided by the agent.

        Returns:
            The absolute path if it's safe, otherwise None.
        """
        # Normalize the path (e.g., handle '..')
        abs_path = os.path.abspath(os.path.join(self.working_dir, path))

        # Security check: Ensure the resolved path is still within the working directory
        if os.path.commonpath([self.working_dir, abs_path]) != self.working_dir:
            print(f"Error: Attempted access outside the working directory: {path}", file=sys.stderr)
            return None
        return abs_path

    def _confirm_write_action(self, action: str, path: str, reason: str, content: Optional[str] = None) -> bool:
        """Gets user confirmation for write/append actions."""
        print("-" * 50, file=sys.stderr)
        print(f"🤖 Agent proposes file action:", file=sys.stderr)
        print(f"   Action: {action.upper()}", file=sys.stderr)
        print(f"   Path: {path}", file=sys.stderr)
        print(f"   Reason: {reason}", file=sys.stderr)
        if content is not None:
             # Show only a preview for potentially long content
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

    def __call__(self, action: str, path: str, reason: str, content: Optional[str] = None) -> str:
        """
        Performs the requested file operation after validation and confirmation.

        Args:
            action: The operation ('read', 'write', 'append', 'list').
            path: The relative path within the working directory.
            reason: Justification for the action.
            content: Data for 'write'/'append'.

        Returns:
            A string indicating success, failure, or the requested data (file content/listing).
        """
        safe_path = self._resolve_path(path)
        if not safe_path:
            return f"Error: Invalid or disallowed path '{path}'. Operations confined to '{self.working_dir}'."

        try:
            if action == "read":
                if not os.path.exists(safe_path):
                    return f"Error: File not found at '{path}'."
                if not os.path.isfile(safe_path):
                     return f"Error: '{path}' is not a file."
                with open(safe_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                return f"Successfully read content from '{path}':\n{file_content}"

            elif action == "list":
                target_path = safe_path
                # If path is a file, list its parent directory
                if os.path.isfile(target_path):
                     target_path = os.path.dirname(target_path)
                # If the directory doesn't exist after resolving
                if not os.path.exists(target_path) or not os.path.isdir(target_path):
                     # Check if the original path existed but wasn't a dir
                     if os.path.exists(safe_path):
                         return f"Error: '{path}' exists but is not a directory."
                     else:
                         return f"Error: Directory not found at '{path}'."

                entries = os.listdir(target_path)
                return f"Successfully listed contents of directory '{os.path.relpath(target_path, self.working_dir)}':\n" + "\n".join(entries)


            elif action == "write" or action == "append":
                if content is None:
                    return f"Error: 'content' is required for '{action}' action."

                # Ensure the target directory exists for writing the file
                parent_dir = os.path.dirname(safe_path)
                if not os.path.exists(parent_dir):
                    try:
                        os.makedirs(parent_dir)
                    except OSError as e:
                        return f"Error: Could not create directory '{os.path.dirname(path)}': {e}"
                elif not os.path.isdir(parent_dir):
                     return f"Error: Cannot create file, '{os.path.dirname(path)}' is not a directory."


                # --- HUMAN IN THE LOOP ---
                if not self._confirm_write_action(action, path, reason, content):
                    return f"User rejected the '{action}' operation on '{path}'."
                # --- END HITL ---

                mode = 'w' if action == 'write' else 'a'
                with open(safe_path, mode, encoding='utf-8') as f:
                    f.write(content)
                return f"Successfully performed '{action}' on file '{path}'."

            else:
                # Should not happen due to schema validation, but good practice
                return f"Error: Unknown action '{action}'."

        except IOError as e:
            return f"Error performing '{action}' on '{path}': {e}"
        except Exception as e:
            # Catch unexpected errors
            print(f"Unexpected error in FileManager: {e}", file=sys.stderr)
            return f"Unexpected error during file operation: {e}"

# Example usage (for testing the tool directly)
if __name__ == "__main__":
    # Create a dummy workspace for testing
    if not os.path.exists("test_workspace"):
        os.makedirs("test_workspace")
    with open("test_workspace/existing_file.txt", "w") as f:
        f.write("Initial content.")

    fm = FileManager(working_dir="test_workspace")

    # Test List
    print(fm(action="list", path=".", reason="List base directory"))
    # Test Write (will prompt)
    print(fm(action="write", path="new_notes.txt", content="This is a test note.", reason="Creating a test note"))
    # Test Read
    print(fm(action="read", path="new_notes.txt", reason="Reading the test note"))
    # Test Append (will prompt)
    print(fm(action="append", path="new_notes.txt", content="\nAdding more info.", reason="Appending to the test note"))
    # Test Read again
    print(fm(action="read", path="new_notes.txt", reason="Reading the appended note"))
    # Test Read existing
    print(fm(action="read", path="existing_file.txt", reason="Reading pre-existing file"))
     # Test List specific sub-directory (will fail initially)
    print(fm(action="list", path="subdir", reason="List non-existent subdir"))
    # Test Write to subdir (will create dir and prompt for file write)
    print(fm(action="write", path="subdir/another_note.txt", content="Note in subdir", reason="Create note in subdir"))
    # Test List subdir again
    print(fm(action="list", path="subdir", reason="List subdir after creation"))

    # Test path traversal attempt, should be blocked
    print("-----\nThe following operation should be blocked due to unauthorized path traversal:")
    print(fm(action="read", path="../outside_file.txt", reason="Attempting path traversal"))

    # Clean up test workspace (optional)
    import shutil
    shutil.rmtree("test_workspace")
