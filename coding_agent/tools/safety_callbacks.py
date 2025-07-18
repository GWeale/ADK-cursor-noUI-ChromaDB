from google.adk.tools import ToolContext
from typing import Dict, Any, Optional, Callable
import datetime
import re
import os
from pathlib import Path

class SecurityValidator:
    """Security validation for coding agent operations"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root).resolve()
        
        # Define dangerous patterns
        self.dangerous_paths = [
            r"\.\.\/",  # Directory traversal
            r"\/etc\/",  # System directories
            r"\/var\/",
            r"\/usr\/",
            r"\/bin\/",
            r"\/sbin\/",
            r"~\/\.ssh",  # SSH keys
            r"~\/\.aws",  # AWS credentials
            r"\/proc\/",  # Process information
            r"\/sys\/",   # System information
        ]
        
        self.dangerous_operations = [
            "rm -rf",
            "sudo",
            "chmod 777",
            ">/dev/null",
            "2>&1",
            "exec(",
            "eval(",
            "__import__",
            "subprocess",
            "os.system"
        ]
        
        # File extensions that should be treated with extra caution
        self.sensitive_extensions = {
            ".sh", ".bat", ".exe", ".dll", ".so", 
            ".key", ".pem", ".p12", ".pfx",
            ".env", ".config"
        }
    
    def validate_file_path(self, file_path: str) -> Dict[str, Any]:
        """Validate file path for security issues"""
        issues = []
        severity = "info"
        
        # Check for dangerous path patterns
        for pattern in self.dangerous_paths:
            if re.search(pattern, file_path, re.IGNORECASE):
                issues.append(f"Dangerous path pattern detected: {pattern}")
                severity = "error"
        
        # Check if path is outside project root
        try:
            abs_path = os.path.abspath(os.path.join(self.project_root, file_path))
            if not abs_path.startswith(str(self.project_root)):
                issues.append("Path is outside project directory")
                severity = "error"
        except Exception as e:
            issues.append(f"Invalid path: {e}")
            severity = "error"
        
        # Check for sensitive file extensions
        file_ext = Path(file_path).suffix.lower()
        if file_ext in self.sensitive_extensions:
            issues.append(f"Sensitive file type: {file_ext}")
            if severity == "info":
                severity = "warning"
        
        return {
            "valid": severity != "error",
            "severity": severity,
            "issues": issues,
            "file_path": file_path
        }
    
    def validate_content(self, content: str) -> Dict[str, Any]:
        """Validate content for dangerous operations"""
        issues = []
        severity = "info"
        
        # Check for dangerous operations in content
        content_lower = content.lower()
        for operation in self.dangerous_operations:
            if operation.lower() in content_lower:
                issues.append(f"Potentially dangerous operation: {operation}")
                severity = "warning"  # Not blocking, just warning
        
        # Check for very large content (potential DoS)
        if len(content) > 1024 * 1024:  # 1MB
            issues.append("Content is very large (>1MB)")
            if severity == "info":
                severity = "warning"
        
        return {
            "valid": True,  # Content warnings don't block operations
            "severity": severity,
            "issues": issues,
            "content_size": len(content)
        }

def validate_file_operations(tool: Callable, args: Dict[str, Any], tool_context: ToolContext) -> Optional[Dict[str, Any]]:
    """
    Safety callback for file operations
    
    Returns:
        None: Allow operation to proceed
        Dict: Block operation and return this as the result
    """
    # Get project root from environment
    project_root = os.environ.get('ADK_PROJECT_ROOT', os.getcwd())
    validator = SecurityValidator(project_root)
    
    # Log the attempted operation
    operations_log = tool_context.state.get("security_log", [])
    operation_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "tool": tool.__name__,
        "args": {k: str(v)[:100] for k, v in args.items()},  # Truncate long values
        "validation_result": None,
        "action": "pending"
    }
    
    try:
        # Validate file path if present
        file_path = args.get("file_path")
        if file_path:
            path_validation = validator.validate_file_path(file_path)
            operation_entry["validation_result"] = path_validation
            
            if not path_validation["valid"]:
                operation_entry["action"] = "blocked"
                operations_log.append(operation_entry)
                tool_context.state["security_log"] = operations_log[-100:]  # Keep last 100 entries
                
                return {
                    "status": "blocked",
                    "reason": "Security validation failed",
                    "issues": path_validation["issues"],
                    "tool": tool.__name__
                }
        
        # Validate content if present (for write operations)
        content = args.get("content")
        if content:
            content_validation = validator.validate_content(content)
            if operation_entry["validation_result"]:
                operation_entry["validation_result"]["content_validation"] = content_validation
            else:
                operation_entry["validation_result"] = {"content_validation": content_validation}
            
            # Content validation currently doesn't block, just warns
            if content_validation["severity"] in ["warning", "error"]:
                # Store warning in session state
                warnings = tool_context.state.get("security_warnings", [])
                warnings.append({
                    "timestamp": datetime.datetime.now().isoformat(),
                    "tool": tool.__name__,
                    "type": "content_validation",
                    "issues": content_validation["issues"]
                })
                tool_context.state["security_warnings"] = warnings[-50:]
        
        # Operation is allowed
        operation_entry["action"] = "allowed"
        operations_log.append(operation_entry)
        tool_context.state["security_log"] = operations_log[-100:]
        
        # Update security counters
        counters = tool_context.state.get("security_counters", {
            "allowed": 0, "blocked": 0, "warnings": 0
        })
        counters["allowed"] += 1
        if operation_entry.get("validation_result", {}).get("content_validation", {}).get("severity") == "warning":
            counters["warnings"] += 1
        tool_context.state["security_counters"] = counters
        
        return None  # Allow operation
        
    except Exception as e:
        # Log the error
        operation_entry["action"] = "error"
        operation_entry["error"] = str(e)
        operations_log.append(operation_entry)
        tool_context.state["security_log"] = operations_log[-100:]
        
        return {
            "status": "error",
            "message": f"Security validation error: {e}",
            "tool": tool.__name__
        }

def validate_search_operations(tool: Callable, args: Dict[str, Any], tool_context: ToolContext) -> Optional[Dict[str, Any]]:
    """
    Safety callback for search operations - mainly for logging and rate limiting
    """
    # Log search operations for analysis
    search_log = tool_context.state.get("search_security_log", [])
    
    # Check for potential injection patterns in queries
    query = args.get("query", "")
    suspicious_patterns = [
        r"<script",
        r"javascript:",
        r"\bUNION\b",
        r"\bSELECT\b",
        r"\bDROP\b",
        r"\bDELETE\b"
    ]
    
    issues = []
    for pattern in suspicious_patterns:
        if re.search(pattern, query, re.IGNORECASE):
            issues.append(f"Suspicious pattern in query: {pattern}")
    
    search_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "tool": tool.__name__,
        "query": query[:200],  # Truncate long queries
        "issues": issues,
        "action": "blocked" if issues else "allowed"
    }
    
    if issues:
        search_log.append(search_entry)
        tool_context.state["search_security_log"] = search_log[-50:]
        
        return {
            "status": "blocked",
            "reason": "Suspicious query patterns detected",
            "issues": issues,
            "tool": tool.__name__
        }
    
    # Rate limiting: check recent search frequency
    recent_searches = [
        entry for entry in search_log 
        if (datetime.datetime.now() - datetime.datetime.fromisoformat(entry["timestamp"])).seconds < 60
    ]
    
    if len(recent_searches) > 20:  # More than 20 searches per minute
        search_entry["action"] = "rate_limited"
        search_log.append(search_entry)
        tool_context.state["search_security_log"] = search_log[-50:]
        
        return {
            "status": "rate_limited",
            "reason": "Too many search requests",
            "tool": tool.__name__
        }
    
    # Allow the search
    search_log.append(search_entry)
    tool_context.state["search_security_log"] = search_log[-50:]
    
    return None

def get_security_summary(tool_context: ToolContext) -> Dict[str, Any]:
    """Get a summary of security-related activities"""
    return {
        "security_counters": tool_context.state.get("security_counters", {}),
        "recent_security_log": tool_context.state.get("security_log", [])[-10:],
        "recent_warnings": tool_context.state.get("security_warnings", [])[-5:],
        "search_security_log": tool_context.state.get("search_security_log", [])[-10:]
    } 