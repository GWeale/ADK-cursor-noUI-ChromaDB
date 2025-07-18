from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from typing import AsyncGenerator
from .specialized_agents import (
    file_operations_agent,
    indexing_agent, 
    search_analysis_agent,
    code_quality_agent
)

class AdvancedCodeAnalysisAgent(BaseAgent):
    """
    Custom agent that implements complex conditional logic for code analysis.
    
    This agent demonstrates the power of custom BaseAgent implementations
    for scenarios that require sophisticated decision-making and conditional flows.
    """
    
    def __init__(self):
        super().__init__(
            name="advanced_code_analysis_agent",
            description="Advanced code analysis agent with conditional logic for complex workflows"
        )
    
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """
        Custom implementation with conditional logic based on:
        - Current codebase state
        - User request type
        - Previous analysis results
        - Session history
        """
        
        # Store analysis start state
        ctx.session.state["analysis_phase"] = "assessment"
        ctx.session.state["analysis_start_time"] = "2024-01-01T00:00:00"  # Would use real timestamp
        
        # Phase 1: Assessment - Check current state
        has_previous_analysis = bool(ctx.session.state.get("search_history"))
        index_exists = bool(ctx.session.state.get("index_status"))
        
        # Phase 2: Conditional Indexing
        if not index_exists:
            ctx.session.state["analysis_phase"] = "initial_indexing"
            
            # Run indexing agent
            async for event in indexing_agent.run_async(ctx):
                yield event
                
            # Check if indexing was successful
            index_result = ctx.session.state.get("indexing_result")
            if index_result and "error" in str(index_result).lower():
                ctx.session.state["limited_analysis"] = True
            else:
                ctx.session.state["limited_analysis"] = False
        else:
            ctx.session.state["analysis_phase"] = "index_validation"
            
            # Check index freshness through indexer
            async for event in indexing_agent.run_async(ctx):
                # Process events and check for freshness indicators
                if hasattr(event, 'content') and event.content and hasattr(event.content, 'parts') and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            if "fresh" in part.text.lower():
                                ctx.session.state["limited_analysis"] = False
                                break
                            elif "stale" in part.text.lower():
                                ctx.session.state["limited_analysis"] = False
                                break
                yield event
            else:
                ctx.session.state["limited_analysis"] = False
        
        # Phase 3: Intelligent Search Strategy
        ctx.session.state["analysis_phase"] = "search_discovery"
        
        if not ctx.session.state.get("limited_analysis", False):
            # Full search capabilities available
            user_query = ctx.session.state.get("user_query", "")
            
            # Determine search strategy based on query type
            if any(keyword in user_query.lower() for keyword in ["error", "bug", "issue", "problem"]):
                ctx.session.state["search_strategy"] = "diagnostic"
            elif any(keyword in user_query.lower() for keyword in ["how", "what", "where", "understand"]):
                ctx.session.state["search_strategy"] = "exploratory"
            elif any(keyword in user_query.lower() for keyword in ["add", "create", "implement", "build"]):
                ctx.session.state["search_strategy"] = "architectural"
            else:
                ctx.session.state["search_strategy"] = "general"
            
            # Execute search based on strategy
            async for event in search_analysis_agent.run_async(ctx):
                yield event
            
            # Analyze search results to determine next steps
            search_results = ctx.session.state.get("search_analysis_result")
            if search_results and "results" in str(search_results):
                found_files = ctx.session.state.get("discovered_files", [])
                ctx.session.state["files_discovered_count"] = len(found_files)
                
                # Conditional file analysis based on findings
                if len(found_files) > 0:
                    ctx.session.state["analysis_phase"] = "file_analysis"
                    
                    # Focus on most relevant files (up to 3)
                    priority_files = found_files[:3]
                    for i, file_path in enumerate(priority_files, 1):
                        # Set target file in state for the file operations agent
                        ctx.session.state["target_file"] = file_path
                        ctx.session.state["current_file_index"] = i
                        ctx.session.state["total_priority_files"] = len(priority_files)
                        
                        async for event in file_operations_agent.run_async(ctx):
                            yield event
            else:
                ctx.session.state["limited_analysis"] = True
        
        # Phase 4/5: Quality Analysis (conditional based on findings)
        files_analyzed = ctx.session.state.get("accessed_files", {})
        if files_analyzed:
            ctx.session.state["analysis_phase"] = "quality_assessment"
            ctx.session.state["files_analyzed_count"] = len(files_analyzed)
            
            async for event in code_quality_agent.run_async(ctx):
                yield event
                
            # Check quality results and provide recommendations
            diagnostics = ctx.session.state.get("file_diagnostics", {})
            if diagnostics:
                error_count = sum(diag.get("error_count", 0) for diag in diagnostics.values())
                warning_count = sum(diag.get("warning_count", 0) for diag in diagnostics.values())
                
                ctx.session.state["total_errors"] = error_count
                ctx.session.state["total_warnings"] = warning_count
        
        # Phase 6: Synthesis and Recommendations
        ctx.session.state["analysis_phase"] = "synthesis"
        
        # Synthesize findings from all phases
        summary_points = []
        
        # Index status
        if ctx.session.state.get("index_status"):
            summary_points.append("✅ Codebase is indexed and searchable")
        else:
            summary_points.append("⚠️ Codebase indexing may need attention")
        
        # Search findings
        discovered_files = ctx.session.state.get("discovered_files", [])
        if discovered_files:
            summary_points.append(f"📁 Analyzed {len(discovered_files)} relevant files")
        
        # Quality findings
        diagnostics = ctx.session.state.get("file_diagnostics", {})
        if diagnostics:
            total_issues = sum(
                diag.get("error_count", 0) + diag.get("warning_count", 0) 
                for diag in diagnostics.values()
            )
            if total_issues == 0:
                summary_points.append("✅ No code quality issues detected")
            else:
                summary_points.append(f"🔍 Found {total_issues} code quality items to review")
        
        # File operations
        file_ops = ctx.session.state.get("operation_counters", {})
        if file_ops:
            reads = file_ops.get("read", 0)
            writes = file_ops.get("write", 0)
            summary_points.append(f"📄 Performed {reads} reads, {writes} writes")
        
        # Store comprehensive analysis summary
        ctx.session.state["analysis_summary"] = summary_points
        
        # Conditional recommendations based on analysis results
        recommendations = []
        
        if not ctx.session.state.get("index_status"):
            recommendations.append("🔄 Run full codebase indexing for better search capabilities")
        
        if ctx.session.state.get("file_diagnostics"):
            error_files = [
                file_path for file_path, diag in ctx.session.state.get("file_diagnostics", {}).items()
                if diag.get("error_count", 0) > 0
            ]
            if error_files:
                recommendations.append(f"🚨 Fix errors in: {', '.join(error_files[:3])}")
        
        search_strategy = ctx.session.state.get("search_strategy", "general")
        if len(discovered_files) > 5:
            recommendations.append("🔍 Consider more specific search queries to narrow focus")
        
        if not discovered_files and search_strategy != "general":
            recommendations.append("🔎 Try broader search terms to discover relevant code")
        
        # Store final analysis state
        ctx.session.state["analysis_complete"] = True
        ctx.session.state["analysis_timestamp"] = "2024-01-01T00:00:00"  # Would use real timestamp
        ctx.session.state["analysis_recommendations"] = recommendations
        ctx.session.state["analysis_phase"] = "complete"

        # Hello, world!
        print("Hello, world!")
    
    def __str__(self) -> str:
        return f"AdvancedCodeAnalysisAgent(name={self.name})" 