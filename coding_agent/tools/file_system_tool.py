import os
from google.adk.tools import FunctionTool, ToolContext
from typing import Dict, Any
import datetime

# this should point to the workspace root (parent of coding_agent folder)
PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

def _is_path_safe(path: str) -> bool:
    """Checks if the provided path is within the project root."""
    abs_path = os.path.abspath(os.path.join(PROJECT_ROOT, path))
    return abs_path.startswith(PROJECT_ROOT)

def _log_file_operation(tool_context: ToolContext, operation: str, file_path: str, success: bool, details: str = ""):
    """Log file operations to session state for audit trail"""
    operations_log = tool_context.state.get("file_operations_log", [])
    operations_log.append({
        "timestamp": datetime.datetime.now().isoformat(),
        "operation": operation,
        "file_path": file_path,
        "success": success,
        "details": details
    })
    tool_context.state["file_operations_log"] = operations_log
    
    # Update operation counters
    counters = tool_context.state.get("operation_counters", {"read": 0, "write": 0})
    if success:
        counters[operation] = counters.get(operation, 0) + 1
    tool_context.state["operation_counters"] = counters

def read_file(file_path: str, tool_context: ToolContext) -> Dict[str, Any]:
    """Reads the full content of a file if it is within the safe project directory."""
    if not _is_path_safe(file_path):
        error_msg = f"Error: Path '{file_path}' is outside the allowed project directory."
        _log_file_operation(tool_context, "read", file_path, False, "Path outside project directory")
        return {"status": "error", "message": error_msg, "content": None}
    
    try:
        full_path = os.path.join(PROJECT_ROOT, file_path)
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Store file info in session state for context
        file_info = tool_context.state.get("accessed_files", {})
        file_info[file_path] = {
            "last_read": datetime.datetime.now().isoformat(),
            "size": len(content),
            "lines": len(content.split('\n'))
        }
        tool_context.state["accessed_files"] = file_info
        tool_context.state["last_read_file"] = file_path
        
        _log_file_operation(tool_context, "read", file_path, True, f"Read {len(content)} characters")
        return {"status": "success", "content": content, "file_path": file_path}
        
    except FileNotFoundError:
        error_msg = f"Error: File not found at '{file_path}'."
        _log_file_operation(tool_context, "read", file_path, False, "File not found")
        return {"status": "error", "message": error_msg, "content": None}
    except Exception as e:
        error_msg = f"An unexpected error occurred: {e}"
        _log_file_operation(tool_context, "read", file_path, False, str(e))
        return {"status": "error", "message": error_msg, "content": None}

def write_file(file_path: str, content: str, tool_context: ToolContext) -> Dict[str, Any]:
    """Writes content to a file if it is within the safe project directory."""
    if not _is_path_safe(file_path):
        error_msg = f"Error: Path '{file_path}' is outside the allowed project directory."
        _log_file_operation(tool_context, "write", file_path, False, "Path outside project directory")
        return {"status": "error", "message": error_msg}
    
    try:
        full_path = os.path.join(PROJECT_ROOT, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # Check if file exists and store backup info
        file_existed = os.path.exists(full_path)
        original_size = 0
        if file_existed:
            original_size = os.path.getsize(full_path)
        
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Update session state with file modification info
        modified_files = tool_context.state.get("modified_files", {})
        modified_files[file_path] = {
            "last_modified": datetime.datetime.now().isoformat(),
            "new_size": len(content),
            "original_size": original_size,
            "was_new_file": not file_existed
        }
        tool_context.state["modified_files"] = modified_files
        tool_context.state["last_written_file"] = file_path
        
        success_msg = f"Successfully wrote {len(content)} characters to {file_path}."
        _log_file_operation(tool_context, "write", file_path, True, f"Wrote {len(content)} characters")
        return {"status": "success", "message": success_msg, "file_path": file_path}
        
    except Exception as e:
        error_msg = f"An unexpected error occurred while writing: {e}"
        _log_file_operation(tool_context, "write", file_path, False, str(e))
        return {"status": "error", "message": error_msg}

def get_operation_summary(tool_context: ToolContext) -> Dict[str, Any]:
    """Get a summary of all file operations performed in this session"""
    return {
        "operation_counters": tool_context.state.get("operation_counters", {}),
        "accessed_files": tool_context.state.get("accessed_files", {}),
        "modified_files": tool_context.state.get("modified_files", {}),
        "recent_operations": tool_context.state.get("file_operations_log", [])[-10:]  # Last 10 operations
    }

read_file_tool = FunctionTool(read_file)
write_file_tool = FunctionTool(write_file)
operation_summary_tool = FunctionTool(get_operation_summary) 