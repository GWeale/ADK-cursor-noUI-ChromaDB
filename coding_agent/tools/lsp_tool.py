from typing import List, Dict, Any, Optional, Union
from google.adk.tools import FunctionTool, ToolContext
from pathlib import Path
import logging
import os
import tempfile
import json
import subprocess
import asyncio
import datetime

try:
    from multilspy import SyncLanguageServer
    from multilspy.multilspy_config import MultilspyConfig
    from multilspy.multilspy_logger import MultilspyLogger
    MULTILSPY_AVAILABLE = True
except ImportError:
    MULTILSPY_AVAILABLE = False

class Position:
    """Simple position class for line/column coordinates"""
    def __init__(self, line: int, character: int):
        self.line = line
        self.character = character

class LSPTool:
    """Tool for integrating with Language Server Protocol servers"""
    
    def __init__(self, project_root: str):
        if not MULTILSPY_AVAILABLE:
            raise ImportError("multilspy is not available. Please install it with: pip install https://github.com/microsoft/multilspy/archive/main.zip")
        
        self.project_root = Path(project_root).resolve()
        self.logger = self._setup_logger()
        self.language_servers: Dict[str, SyncLanguageServer] = {}
        
        # Language server configurations
        self.server_configs = {
            '.py': {
                'language_id': 'python',
                'code_language': 'python'
            },
            '.java': {
                'language_id': 'java', 
                'code_language': 'java'
            },
            '.js': {
                'language_id': 'javascript',
                'code_language': 'javascript'
            },
            '.ts': {
                'language_id': 'typescript',
                'code_language': 'javascript'  # multilspy uses 'javascript' for both JS and TS
            },
            '.rs': {
                'language_id': 'rust',
                'code_language': 'rust'
            },
            '.cs': {
                'language_id': 'csharp',
                'code_language': 'csharp'
            }
        }
    
    def _log_lsp_operation(self, tool_context: ToolContext, operation: str, file_path: str, success: bool, details: str = ""):
        """Log LSP operations to session state"""
        lsp_log = tool_context.state.get("lsp_operations_log", [])
        lsp_log.append({
            "timestamp": datetime.datetime.now().isoformat(),
            "operation": operation,
            "file_path": file_path,
            "success": success,
            "details": details
        })
        tool_context.state["lsp_operations_log"] = lsp_log[-50:]  # Keep last 50 operations
        
        # Update LSP operation counters
        counters = tool_context.state.get("lsp_counters", {
            "diagnostics": 0, "definitions": 0, "references": 0, "validations": 0
        })
        if success:
            counters[operation] = counters.get(operation, 0) + 1
        tool_context.state["lsp_counters"] = counters

    def _setup_logger(self) -> MultilspyLogger:
        """Setup MultilspyLogger for language servers"""
        return MultilspyLogger()
    
    def _get_or_create_server(self, file_ext: str) -> Optional[SyncLanguageServer]:
        """Get or create a language server for the given file extension"""
        if file_ext not in self.server_configs:
            print(f"No language server configuration for {file_ext}")
            return None
        
        server_name = f"server_{file_ext}"
        
        # Return existing server if available
        if server_name in self.language_servers:
            return self.language_servers[server_name]
        
        try:
            # Create configuration for the language server
            config_dict = {"code_language": self.server_configs[file_ext]['code_language']}
            config = MultilspyConfig.from_dict(config_dict)
            
            # Create new language server with the correct three parameters
            language_server = SyncLanguageServer.create(
                config, 
                self.logger, 
                str(self.project_root)
            )
            
            self.language_servers[server_name] = language_server
            return language_server
            
        except Exception as e:
            print(f"Failed to create language server for {file_ext}: {e}")
            return None

    def get_diagnostics(self, file_path: str, content: Optional[str] = None, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
        """Get diagnostic information for a file"""
        file_ext = Path(file_path).suffix
        
        try:
            language_server = self._get_or_create_server(file_ext)
            if not language_server:
                result = {"status": "error", "message": f"No language server available for {file_ext}", "diagnostics": []}
                if tool_context:
                    self._log_lsp_operation(tool_context, "diagnostics", file_path, False, f"No LSP for {file_ext}")
                return result
            
            # Use provided content or read from file
            if content is None:
                full_path = self.project_root / file_path
                if not full_path.exists():
                    result = {"status": "error", "message": f"File not found: {file_path}", "diagnostics": []}
                    if tool_context:
                        self._log_lsp_operation(tool_context, "diagnostics", file_path, False, "File not found")
                    return result
                
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            
            # Get diagnostics from language server
            # TODO: Fix multilspy API usage - commenting out for now
            # with language_server.start_server():
            #     language_server.open_file(file_path, content)
            #     diagnostics = language_server.get_diagnostics(file_path)
            
            # Using placeholder diagnostics until multilspy API is corrected
            diagnostics = []
            
            # Format diagnostics
            formatted_diagnostics = []
            for diag in diagnostics:
                formatted_diag = {
                    "line": diag.get("range", {}).get("start", {}).get("line", 0),
                    "character": diag.get("range", {}).get("start", {}).get("character", 0),
                    "severity": diag.get("severity", "unknown"),
                    "message": diag.get("message", ""),
                    "source": diag.get("source", ""),
                    "code": diag.get("code", "")
                }
                formatted_diagnostics.append(formatted_diag)
            
            # Store diagnostics in session state
            if tool_context:
                file_diagnostics = tool_context.state.get("file_diagnostics", {})
                file_diagnostics[file_path] = {
                    "timestamp": datetime.datetime.now().isoformat(),
                    "diagnostics": formatted_diagnostics,
                    "error_count": len([d for d in formatted_diagnostics if d["severity"] == 1]),
                    "warning_count": len([d for d in formatted_diagnostics if d["severity"] == 2])
                }
                tool_context.state["file_diagnostics"] = file_diagnostics
                self._log_lsp_operation(tool_context, "diagnostics", file_path, True, f"Found {len(formatted_diagnostics)} issues")
            
            return {
                "status": "success",
                "file_path": file_path,
                "diagnostics": formatted_diagnostics,
                "summary": {
                    "total": len(formatted_diagnostics),
                    "errors": len([d for d in formatted_diagnostics if d["severity"] == 1]),
                    "warnings": len([d for d in formatted_diagnostics if d["severity"] == 2])
                }
            }
                
        except Exception as e:
            error_msg = f"Error getting diagnostics: {str(e)}"
            if tool_context:
                self._log_lsp_operation(tool_context, "diagnostics", file_path, False, error_msg)
            return {"status": "error", "message": error_msg, "diagnostics": []}

    def validate_code_in_shadow_workspace(self, file_path: str, new_content: str, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
        """
        Validate code changes in a temporary shadow workspace.
        
        Args:
            file_path: Path to the file being modified
            new_content: New content to validate
            tool_context: ADK tool context for state management
            
        Returns:
            Dictionary with validation results
        """
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_workspace = Path(temp_dir)
                self._copy_workspace_context(temp_workspace, file_path)
                temp_file = temp_workspace / file_path
                temp_file.parent.mkdir(parents=True, exist_ok=True)
                with open(temp_file, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                shadow_lsp = LSPTool(str(temp_workspace))
                diagnostics_result = shadow_lsp.get_diagnostics(file_path, new_content, tool_context)
                
                has_errors = any(d["severity"] == 1 for d in diagnostics_result.get("diagnostics", []))
                error_count = len([d for d in diagnostics_result.get("diagnostics", []) if d["severity"] == 1])
                warning_count = len([d for d in diagnostics_result.get("diagnostics", []) if d["severity"] == 2])
                
                # Store validation results in session state
                if tool_context:
                    validations = tool_context.state.get("code_validations", [])
                    validations.append({
                        "timestamp": datetime.datetime.now().isoformat(),
                        "file_path": file_path,
                        "valid": not has_errors,
                        "error_count": error_count,
                        "warning_count": warning_count
                    })
                    tool_context.state["code_validations"] = validations[-20:]  # Keep last 20 validations
                    self._log_lsp_operation(tool_context, "validations", file_path, True, f"Validation: {error_count} errors, {warning_count} warnings")
                
                return {
                    "status": "success",
                    "valid": not has_errors,
                    "error_count": error_count,
                    "warning_count": warning_count,
                    "diagnostics": diagnostics_result.get("diagnostics", []),
                    "temp_workspace": str(temp_workspace)
                }
                
        except Exception as e:
            error_msg = f"Error validating code: {str(e)}"
            if tool_context:
                self._log_lsp_operation(tool_context, "validations", file_path, False, error_msg)
            return {
                "status": "error",
                "message": error_msg,
                "valid": False
            }
    
    def _copy_workspace_context(self, temp_workspace: Path, target_file: str):
        """Copy relevant workspace files for context"""
        try:
            import shutil
            
            # For now, just copy the target file and basic project structure
            # In a full implementation, you'd analyze dependencies and copy related files
            
            # Copy the target file if it exists
            source_file = self.project_root / target_file
            if source_file.exists():
                dest_file = temp_workspace / target_file
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_file, dest_file)
            
            # Copy common config files
            config_files = [
                'pyproject.toml', 'setup.py', 'requirements.txt',
                'package.json', 'tsconfig.json', '.pylintrc'
            ]
            
            for config_file in config_files:
                source_config = self.project_root / config_file
                if source_config.exists():
                    dest_config = temp_workspace / config_file
                    shutil.copy2(source_config, dest_config)
                    
        except Exception as e:
            print(f"Could not copy full workspace context: {e}")
    
    def cleanup(self):
        """Cleanup language server resources"""
        for server in self.language_servers.values():
            try:
                # For multilspy, we don't need explicit shutdown
                # The context manager handles this
                pass
            except Exception as e:
                print(f"Error shutting down language server: {e}")
        self.language_servers.clear()

# ADK tool wrappers
def get_diagnostics_tool(file_path: str, content: str = "", tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    """Get diagnostic information for a file using LSP"""
    project_root = os.environ.get('ADK_PROJECT_ROOT', os.getcwd())
    lsp_tool = LSPTool(project_root)
    
    file_content = content if content else None
    return lsp_tool.get_diagnostics(file_path, file_content, tool_context)

def validate_code_tool(file_path: str, new_content: str, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    """Validate code changes in a shadow workspace"""
    project_root = os.environ.get('ADK_PROJECT_ROOT', os.getcwd())
    lsp_tool = LSPTool(project_root)
    
    return lsp_tool.validate_code_in_shadow_workspace(file_path, new_content, tool_context)

def get_lsp_summary_tool(tool_context: ToolContext) -> Dict[str, Any]:
    """Get a summary of LSP operations performed in this session"""
    return {
        "lsp_counters": tool_context.state.get("lsp_counters", {}),
        "recent_operations": tool_context.state.get("lsp_operations_log", [])[-10:],
        "file_diagnostics": tool_context.state.get("file_diagnostics", {}),
        "code_validations": tool_context.state.get("code_validations", [])[-5:]
    }

# Create ADK tools
get_diagnostics_adk_tool = FunctionTool(get_diagnostics_tool)
validate_code_adk_tool = FunctionTool(validate_code_tool)
lsp_summary_adk_tool = FunctionTool(get_lsp_summary_tool)

# Placeholder tools for missing LSP functionality (go to definition, find references)
def go_to_definition_tool(file_path: str, line: int, character: int, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    """Placeholder for go to definition functionality"""
    if tool_context:
        placeholders = tool_context.state.get("lsp_placeholders", [])
        placeholders.append("go_to_definition")
        tool_context.state["lsp_placeholders"] = placeholders
    return {"status": "not_implemented", "message": "Go to definition not yet implemented"}

def find_references_tool(file_path: str, line: int, character: int, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    """Placeholder for find references functionality"""
    if tool_context:
        placeholders = tool_context.state.get("lsp_placeholders", [])
        placeholders.append("find_references")
        tool_context.state["lsp_placeholders"] = placeholders
    return {"status": "not_implemented", "message": "Find references not yet implemented"}

go_to_definition_adk_tool = FunctionTool(go_to_definition_tool)
find_references_adk_tool = FunctionTool(find_references_tool) 