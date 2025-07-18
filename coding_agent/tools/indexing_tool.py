from google.adk.tools import FunctionTool, ToolContext
import os
from pathlib import Path
from typing import Dict, Any
import datetime

def index_codebase_tool(tool_context: ToolContext) -> Dict[str, Any]:
    """Index the entire codebase and create searchable embeddings"""
    project_root = Path(os.environ.get('ADK_PROJECT_ROOT', os.getcwd()))
    
    try:
        from coding_agent.tools.indexing_agent import IndexingAgent
        
        # Log the indexing operation
        indexing_log = tool_context.state.get("indexing_log", [])
        operation_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "operation": "full_index",
            "status": "started"
        }
        
        indexer = IndexingAgent(str(project_root))
        result = indexer.index_codebase()
        
        # Update operation entry with results
        operation_entry["status"] = "completed"
        operation_entry["files_indexed"] = str(len(result['indexed_files']))
        operation_entry["total_elements"] = str(result['total_elements'])
        operation_entry["errors"] = str(len(result.get('errors', [])))
        
        indexing_log.append(operation_entry)
        tool_context.state["indexing_log"] = indexing_log[-10:]  # Keep last 10 operations
        
        # Store indexing status and results in session state
        tool_context.state["index_status"] = {
            "last_indexed": datetime.datetime.now().isoformat(),
            "files_count": len(result['indexed_files']),
            "elements_count": result['total_elements'],
            "has_errors": len(result.get('errors', [])) > 0
        }
        
        # Store list of indexed files for reference
        tool_context.state["indexed_files"] = result['indexed_files']
        
        # Update indexing counters
        counters = tool_context.state.get("indexing_counters", {"full_index": 0, "incremental_index": 0})
        counters["full_index"] = counters.get("full_index", 0) + 1
        tool_context.state["indexing_counters"] = counters
        
        success_msg = f"Indexing complete! Files indexed: {len(result['indexed_files'])}, Code elements found: {result['total_elements']}"
        if result.get('errors'):
            success_msg += f", Errors: {len(result['errors'])}"
        success_msg += "\nYou can now search the codebase using semantic queries!"
        
        return {
            "status": "success",
            "message": success_msg,
            "files_indexed": len(result['indexed_files']),
            "total_elements": result['total_elements'],
            "errors": result.get('errors', []),
            "indexed_files": result['indexed_files']
        }
        
    except Exception as e:
        # Log the error
        operation_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "operation": "full_index",
            "status": "failed",
            "error": str(e)
        }
        
        indexing_log = tool_context.state.get("indexing_log", [])
        indexing_log.append(operation_entry)
        tool_context.state["indexing_log"] = indexing_log[-10:]
        
        return {
            "status": "error",
            "message": f"Indexing failed: {str(e)}",
            "files_indexed": 0,
            "total_elements": 0,
            "errors": [str(e)]
        }

def get_index_status_tool(tool_context: ToolContext) -> Dict[str, Any]:
    """Get the current status of the codebase index"""
    index_status = tool_context.state.get("index_status", {})
    indexing_log = tool_context.state.get("indexing_log", [])
    indexed_files = tool_context.state.get("indexed_files", [])
    
    return {
        "index_exists": bool(index_status),
        "last_indexed": index_status.get("last_indexed", "Never"),
        "files_count": index_status.get("files_count", 0),
        "elements_count": index_status.get("elements_count", 0),
        "has_errors": index_status.get("has_errors", False),
        "recent_operations": indexing_log[-5:],  # Last 5 operations
        "indexed_files_sample": indexed_files[:10],  # First 10 files as sample
        "total_indexed_files": len(indexed_files)
    }

def check_index_freshness_tool(tool_context: ToolContext) -> Dict[str, Any]:
    """Check if the index is fresh or needs updating"""
    project_root = Path(os.environ.get('ADK_PROJECT_ROOT', os.getcwd()))
    index_status = tool_context.state.get("index_status", {})
    
    if not index_status:
        return {
            "fresh": False,
            "reason": "No index found",
            "recommendation": "Run full indexing"
        }
    
    last_indexed_str = index_status.get("last_indexed")
    if not last_indexed_str:
        return {
            "fresh": False,
            "reason": "Index timestamp missing",
            "recommendation": "Run full indexing"
        }
    
    try:
        last_indexed = datetime.datetime.fromisoformat(last_indexed_str)
        hours_since_index = (datetime.datetime.now() - last_indexed).total_seconds() / 3600
        
        # Check if index is older than 24 hours
        if hours_since_index > 24:
            return {
                "fresh": False,
                "reason": f"Index is {hours_since_index:.1f} hours old",
                "recommendation": "Consider re-indexing"
            }
        
        # Check if there are new/modified files since last index
        # This is a simplified check - in production you'd compare file modification times
        indexed_files = set(tool_context.state.get("indexed_files", []))
        
        # Count current files
        code_extensions = {'.py', '.js', '.ts', '.tsx', '.jsx', '.md'}
        current_files = []
        for ext in code_extensions:
            current_files.extend(project_root.rglob(f"*{ext}"))
        
        ignore_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', '.adk_index'}
        current_files = [
            str(f.relative_to(project_root)) 
            for f in current_files 
            if not any(ignore_dir in f.parts for ignore_dir in ignore_dirs)
        ]
        current_files_set = set(current_files)
        
        new_files = current_files_set - indexed_files
        deleted_files = indexed_files - current_files_set
        
        if new_files or deleted_files:
            return {
                "fresh": False,
                "reason": f"{len(new_files)} new files, {len(deleted_files)} deleted files",
                "recommendation": "Run incremental or full indexing",
                "new_files": list(new_files)[:5],  # Show first 5
                "deleted_files": list(deleted_files)[:5]
            }
        
        return {
            "fresh": True,
            "reason": f"Index is {hours_since_index:.1f} hours old and up to date",
            "last_indexed": last_indexed_str
        }
        
    except Exception as e:
        return {
            "fresh": False,
            "reason": f"Error checking freshness: {str(e)}",
            "recommendation": "Run full indexing"
        }

# Create ADK tools
index_codebase_adk_tool = FunctionTool(index_codebase_tool)
get_index_status_adk_tool = FunctionTool(get_index_status_tool)
check_index_freshness_adk_tool = FunctionTool(check_index_freshness_tool) 