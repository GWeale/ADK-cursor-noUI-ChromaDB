from typing import List, Dict, Any, Optional, Union
from google.adk.tools import FunctionTool, ToolContext
from sentence_transformers import SentenceTransformer
import chromadb
from pathlib import Path
import os
import datetime

class VectorSearchTool:
    """Tool for semantic search over the indexed codebase"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Initialize ChromaDB client with persistent storage
        persist_dir = str(self.project_root / ".adk_index")
        if not os.path.exists(persist_dir):
            print(f"Warning: Index directory {persist_dir} does not exist. Run indexing first.")
        
        self.client = chromadb.PersistentClient(path=persist_dir)
        
        # Get existing collections
        try:
            self.code_collection = self.client.get_collection("code_elements")
            self.file_collection = self.client.get_collection("file_summaries")
        except ValueError:
            # Collections don't exist yet
            self.code_collection = None
            self.file_collection = None
    
    def _log_search(self, tool_context: ToolContext, query: str, search_type: str, results_count: int, successful: bool):
        """Log search operations to session state"""
        search_history = tool_context.state.get("search_history", [])
        search_history.append({
            "timestamp": datetime.datetime.now().isoformat(),
            "query": query,
            "search_type": search_type,
            "results_count": results_count,
            "successful": successful
        })
        tool_context.state["search_history"] = search_history[-50:]  # Keep last 50 searches
        
        # Update search counters
        counters = tool_context.state.get("search_counters", {})
        counters[search_type] = counters.get(search_type, 0) + 1
        tool_context.state["search_counters"] = counters
    
    def semantic_search(self, query: str, max_results: int = 5, file_type_filter: Optional[str] = None, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
        if not self.code_collection:
            if tool_context:
                self._log_search(tool_context, query, "semantic_code", 0, False)
            return {"status": "error", "message": "No code index found. Please run indexing first.", "results": []}
            
        try:
            # Create query embedding
            query_embedding = self.embedding_model.encode(query).tolist()
            
            if file_type_filter and file_type_filter.strip():
                results = self.code_collection.query(
                    query_embeddings=[query_embedding],
                    n_results=max_results,
                    where={"file_type": file_type_filter}
                )
            else:
                results = self.code_collection.query(
                    query_embeddings=[query_embedding],
                    n_results=max_results
                )
            
            documents = results.get('documents', [])
            metadatas = results.get('metadatas', [])
            distances = results.get('distances', [])
            
            # Safely check for empty results
            if not documents or not documents[0]:
                if tool_context:
                    self._log_search(tool_context, query, "semantic_code", 0, True)
                return {"status": "success", "message": f"No results found for query: '{query}'", "results": []}
            
            formatted_results = []
            doc_list = documents[0]
            meta_list = metadatas[0] if metadatas else []
            dist_list = distances[0] if distances else []
            
            for i, doc in enumerate(doc_list):
                meta = meta_list[i] if i < len(meta_list) else {}
                dist = dist_list[i] if i < len(dist_list) else 1.0
                
                result = {
                    "rank": i + 1,
                    "similarity_score": 1 - dist,  # Convert distance to similarity
                    "element_name": meta.get("name", "Unknown"),
                    "element_type": meta.get("element_type", "Unknown"),
                    "file_path": meta.get("file_path", "Unknown"),
                    "start_line": meta.get("start_line", 0),
                    "end_line": meta.get("end_line", 0),
                    "content_preview": doc[:200] + "..." if len(doc) > 200 else doc,
                    "docstring": meta.get("docstring", "")
                }
                formatted_results.append(result)
            
            # Store search results in session state for reference
            if tool_context:
                self._log_search(tool_context, query, "semantic_code", len(formatted_results), True)
                tool_context.state["last_search_results"] = formatted_results
                tool_context.state["last_search_query"] = query
                
                # Build cumulative knowledge
                found_files = set(tool_context.state.get("discovered_files", []))
                for result in formatted_results:
                    found_files.add(result["file_path"])
                tool_context.state["discovered_files"] = list(found_files)
            
            return {
                "status": "success", 
                "query": query,
                "results_count": len(formatted_results),
                "results": formatted_results
            }
            
        except Exception as e:
            if tool_context:
                self._log_search(tool_context, query, "semantic_code", 0, False)
            return {"status": "error", "message": f"Search failed: {str(e)}", "results": []}

    def find_files_by_content(self, query: str, max_results: int = 5, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
        if not self.file_collection:
            if tool_context:
                self._log_search(tool_context, query, "file_search", 0, False)
            return {"status": "error", "message": "No file index found. Please run indexing first.", "results": []}
        
        try:
            query_embedding = self.embedding_model.encode(query).tolist()
            
            results = self.file_collection.query(
                query_embeddings=[query_embedding],
                n_results=max_results
            )
            
            documents = results.get('documents', [])
            metadatas = results.get('metadatas', [])
            distances = results.get('distances', [])
            
            if not documents or not documents[0]:
                if tool_context:
                    self._log_search(tool_context, query, "file_search", 0, True)
                return {"status": "success", "message": f"No files found for query: '{query}'", "results": []}
            
            formatted_results = []
            doc_list = documents[0]
            meta_list = metadatas[0] if metadatas else []
            dist_list = distances[0] if distances else []
            
            for i, doc in enumerate(doc_list):
                meta = meta_list[i] if i < len(meta_list) else {}
                dist = dist_list[i] if i < len(dist_list) else 1.0
                
                result = {
                    "rank": i + 1,
                    "similarity_score": 1 - dist,
                    "file_path": meta.get("file_path", "Unknown"),
                    "file_type": meta.get("file_type", "Unknown"),
                    "element_count": meta.get("element_count", 0),
                    "summary": doc[:300] + "..." if len(doc) > 300 else doc
                }
                formatted_results.append(result)
            
            if tool_context:
                self._log_search(tool_context, query, "file_search", len(formatted_results), True)
                tool_context.state["last_file_search_results"] = formatted_results
                
                # Update discovered files
                found_files = set(tool_context.state.get("discovered_files", []))
                for result in formatted_results:
                    found_files.add(result["file_path"])
                tool_context.state["discovered_files"] = list(found_files)
            
            return {
                "status": "success",
                "query": query, 
                "results_count": len(formatted_results),
                "results": formatted_results
            }
            
        except Exception as e:
            if tool_context:
                self._log_search(tool_context, query, "file_search", 0, False)
            return {"status": "error", "message": f"File search failed: {str(e)}", "results": []}

    def get_file_structure(self, file_path: str, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
        if not self.code_collection:
            return {"status": "error", "message": "No code index found. Please run indexing first.", "elements": []}
        
        try:
            # Search for all elements from this specific file
            results = self.code_collection.get(
                where={"file_path": file_path}
            )
            
            if not results or not results.get('metadatas'):
                return {"status": "success", "message": f"No indexed elements found for file: {file_path}", "elements": []}
            
            elements = []
            metadatas = results.get('metadatas', [])
            if metadatas:
                for meta in metadatas:
                    element = {
                        "name": meta.get("name", "Unknown"),
                        "type": meta.get("element_type", "Unknown"),
                        "start_line": meta.get("start_line", 0),
                        "end_line": meta.get("end_line", 0),
                        "docstring": meta.get("docstring", "")
                    }
                    elements.append(element)
            
            # Sort by line number
            elements.sort(key=lambda x: x["start_line"])
            
            # Store file context in session state
            if tool_context:
                file_contexts = tool_context.state.get("file_contexts", {})
                file_contexts[file_path] = {
                    "timestamp": datetime.datetime.now().isoformat(),
                    "element_count": len(elements),
                    "elements": elements
                }
                tool_context.state["file_contexts"] = file_contexts
                tool_context.state["last_analyzed_file"] = file_path
            
            return {
                "status": "success",
                "file_path": file_path,
                "element_count": len(elements),
                "elements": elements
            }
            
        except Exception as e:
            return {"status": "error", "message": f"Failed to get file structure: {str(e)}", "elements": []}

def search_code_tool(query: str, max_results: int = 10, element_types: str = "", tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    """Search for code elements using semantic similarity"""
    # Get project root from environment or use default
    import os
    project_root = os.environ.get('ADK_PROJECT_ROOT', os.getcwd())
    
    search_tool = VectorSearchTool(project_root)
    
    # Parse element_types if provided
    types_list = None
    if element_types:
        types_list = [t.strip() for t in element_types.split(',') if t.strip()]
    
    # Since semantic_search expects file_type_filter, not element types, use first type if available
    file_filter = types_list[0] if types_list else None
    return search_tool.semantic_search(query, max_results, file_filter, tool_context)

def search_files_tool(query: str, max_results: int = 5, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    """Search for files based on their summaries"""
    import os
    project_root = os.environ.get('ADK_PROJECT_ROOT', os.getcwd())
    
    search_tool = VectorSearchTool(project_root)
    return search_tool.find_files_by_content(query, max_results, tool_context)

def get_file_context_tool(file_path: str, max_elements: int = 20, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    """Get context about a specific file including all its code elements"""
    import os
    project_root = os.environ.get('ADK_PROJECT_ROOT', os.getcwd())
    
    search_tool = VectorSearchTool(project_root)
    return search_tool.get_file_structure(file_path, tool_context)

def get_search_summary_tool(tool_context: ToolContext) -> Dict[str, Any]:
    """Get a summary of all search operations performed in this session"""
    return {
        "search_counters": tool_context.state.get("search_counters", {}),
        "discovered_files": tool_context.state.get("discovered_files", []),
        "recent_searches": tool_context.state.get("search_history", [])[-10:],  # Last 10 searches
        "last_search_query": tool_context.state.get("last_search_query", ""),
        "analyzed_files": list(tool_context.state.get("file_contexts", {}).keys())
    }

# Create the ADK tools
search_code_adk_tool = FunctionTool(search_code_tool)
search_files_adk_tool = FunctionTool(search_files_tool) 
get_file_context_adk_tool = FunctionTool(get_file_context_tool)
search_summary_adk_tool = FunctionTool(get_search_summary_tool) 
