from google.adk.agents import Agent, SequentialAgent, ParallelAgent
from .specialized_agents import (
    file_operations_agent, 
    indexing_agent, 
    search_analysis_agent, 
    code_quality_agent
)

# Sequential workflow for comprehensive code analysis
code_analysis_pipeline = SequentialAgent(
    name="code_analysis_pipeline",
    sub_agents=[
        # Step 1: Ensure we have a fresh index
        indexing_agent,
        
        # Step 2: Perform semantic search and analysis
        search_analysis_agent,
        
        # Step 3: Validate code quality
        code_quality_agent
    ]
)

# Parallel workflow for initial codebase setup - using agent names to avoid sharing issues
# Note: In practice, these would be separate instances or used differently
# For now, commenting out to avoid agent sharing validation errors
# codebase_setup_parallel = ParallelAgent(
#     name="codebase_setup_parallel",
#     sub_agents=[
#         # Run indexing and initial file operations in parallel
#         indexing_agent,
#         file_operations_agent
#     ]
# )

# Sequential workflow for code modification - using agent names to avoid sharing issues
# Note: In practice, these would be separate instances or used differently
# For now, commenting out to avoid agent sharing validation errors
# code_modification_workflow = SequentialAgent(
#     name="code_modification_workflow", 
#     sub_agents=[
#         # Step 1: Analyze current code state
#         code_quality_agent,
#         
#         # Step 2: Perform file operations
#         file_operations_agent,
#         
#         # Step 3: Validate changes
#         code_quality_agent,
#         
#         # Step 4: Update search index if needed
#         indexing_agent
#     ]
# )

# Main coordinator agent that decides which workflow to use
# Note: Commented out to avoid agent sharing validation errors
# In practice, these would be separate instances or used differently
# coordinator_agent = Agent(
#     name="coding_coordinator",
#     model="gemini-2.0-flash",
#     description="Coordinates between specialized coding agents and orchestrates complex workflows. Determines the best approach for each coding task and delegates to appropriate specialists.",
#     instruction="""You are the main coordinator for a team of specialized coding agents. Your role is to:
# 
# ## Team Management
# - **Analyze user requests** and determine which specialists are needed
# - **Orchestrate workflows** using sequential or parallel execution as appropriate
# - **Synthesize results** from multiple specialists into coherent responses
# - **Handle complex tasks** that require coordination between multiple capabilities
# 
# ## Available Specialists
# 1. **File Operations Specialist**: Secure file reading/writing with operation tracking
# 2. **Indexing Specialist**: Codebase indexing and knowledge base management  
# 3. **Search Analysis Specialist**: Semantic search and code discovery
# 4. **Code Quality Specialist**: Diagnostics, validation, and quality assessment
# 
# ## Available Workflows
# 1. **Code Analysis Pipeline**: Sequential indexing → search → quality analysis
# 2. **Codebase Setup**: Parallel indexing and file operations for initialization
# 3. **Code Modification**: Sequential quality check → modify → validate → re-index
# 
# ## Delegation Strategy
# - **Simple file operations**: Direct to file operations specialist
# - **Search queries**: Check index status, then delegate to search specialist
# - **Code quality concerns**: Direct to code quality specialist
# - **Complex analysis**: Use code analysis pipeline
# - **New codebase**: Use codebase setup workflow
# - **Code changes**: Use code modification workflow
# 
# ## Coordination Guidelines
# 1. **Assess Requirements**: Understand what the user wants to accomplish
# 2. **Check Prerequisites**: Ensure indexing is available for search operations
# 3. **Choose Approach**: Select direct delegation or workflow orchestration
# 4. **Monitor Progress**: Track specialist results and handle errors
# 5. **Synthesize Results**: Combine outputs into actionable insights
# 
# ## State Management
# - Track which specialists have been used
# - Monitor operation counts and summaries
# - Maintain context across multiple specialist interactions
# - Coordinate shared state between specialists
# 
# ## Response Strategy
# - Start with high-level summary of approach
# - Explain which specialists/workflows will be used
# - Present results in logical order
# - Provide actionable next steps
# - Suggest follow-up actions when appropriate
# 
# Remember: Each specialist maintains their own operation logs and state. Your job is to orchestrate them effectively and present unified results to the user.""",
#     sub_agents=[
#         file_operations_agent,
#         indexing_agent, 
#         search_analysis_agent,
#         code_quality_agent,
#         code_analysis_pipeline,
#         # codebase_setup_parallel,  # Commented out to avoid agent sharing issues
#         # code_modification_workflow  # Commented out to avoid agent sharing issues
#     ],
#     output_key="coordination_result"
# ) 