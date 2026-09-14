from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum
import json
import inspect


class AgentType(str, Enum):
    LLM = "llm"
    ROOT = "root"
    BUILDER = "builder"
    RUNNER = "runner"


class ToolCategory(str, Enum):
    CRM_QUERY = "crm_query"
    DATA_ANALYSIS = "data_analysis"
    CHARTING = "charting"
    PDF_GENERATION = "pdf_generation"
    RESEARCH = "research"
    CRM_ACTION = "crm_action"
    CODE_EXECUTION = "code_execution"
    BASH = "bash"


@dataclass
class Tool:
    name: str
    category: ToolCategory
    endpoint: str
    description: str
    params_schema: Dict[str, Any]


@dataclass
class Agent:
    type: AgentType
    name: str
    tools: List[Tool]
    description: str


RUNNER_TOOLS = [
    Tool("query_crm", ToolCategory.CRM_QUERY, "/api/agents/runner/query_crm", "Run SQL on CRM database", {"query": "str"}),
    Tool("execute_python", ToolCategory.DATA_ANALYSIS, "/api/agents/runner/execute_python", "Run Python with pandas, matplotlib, seaborn", {"code": "str", "timeout": "int"}),
    Tool("create_chart", ToolCategory.CHARTING, "/api/agents/runner/create_chart", "Generate chart with matplotlib/seaborn", {"code": "str", "output_path": "str"}),
    Tool("generate_pdf", ToolCategory.PDF_GENERATION, "/api/agents/runner/generate_pdf", "Create PDF report", {"content": "str", "title": "str", "output_path": "str"}),
    Tool("bash", ToolCategory.BASH, "/api/agents/runner/bash", "Execute shell command", {"command": "str", "timeout": "int"}),
]

ROOT_TOOLS = [
    Tool("search_crm", ToolCategory.CRM_QUERY, "/api/agents/root/search_crm", "Search CRM records", {"query": "str", "limit": "int"}),
    Tool("research_person", ToolCategory.RESEARCH, "/api/agents/root/research_person", "Research a person", {"name": "str", "company": "str"}),
    Tool("research_company", ToolCategory.RESEARCH, "/api/agents/root/research_company", "Research a company", {"name": "str"}),
    Tool("identify_contact", ToolCategory.RESEARCH, "/api/agents/root/identify_contact", "Identify contact from partial info", {"email": "str", "name": "str"}),
    Tool("create_crm_activity", ToolCategory.CRM_ACTION, "/api/agents/root/create_crm_activity", "Log CRM activity", {"contactId": "str", "type": "str", "body": "str"}),
    Tool("record_fact", ToolCategory.CRM_ACTION, "/api/agents/root/record_fact", "Record a fact about entity", {"entity_type": "str", "entity_id": "str", "fact": "str"}),
]

BUILDER_TOOLS = [
    Tool("bash", ToolCategory.CODE_EXECUTION, "/api/agents/builder/bash", "Execute shell command", {"command": "str"}),
    Tool("write_file", ToolCategory.CODE_EXECUTION, "/api/agents/builder/write_file", "Write file", {"path": "str", "content": "str"}),
    Tool("read_file", ToolCategory.CODE_EXECUTION, "/api/agents/builder/read_file", "Read file", {"path": "str"}),
    Tool("glob", ToolCategory.CODE_EXECUTION, "/api/agents/builder/glob", "Find files by pattern", {"pattern": "str"}),
    Tool("grep", ToolCategory.CODE_EXECUTION, "/api/agents/builder/grep", "Search in files", {"pattern": "str"}),
]

AGENTS = {
    AgentType.RUNNER: Agent(AgentType.RUNNER, "Runner", RUNNER_TOOLS, "Data analysis, charting, PDF generation, CRM queries, code execution"),
    AgentType.ROOT: Agent(AgentType.ROOT, "Root", ROOT_TOOLS, "CRM intelligence, research, contact/company enrichment, CRM actions"),
    AgentType.BUILDER: Agent(AgentType.BUILDER, "Builder", BUILDER_TOOLS, "Code development, file operations, project scaffolding"),
    AgentType.LLM: Agent(AgentType.LLM, "LLM", [], "General conversation, reasoning, planning"),
}


@dataclass
class PlanStep:
    agent: AgentType
    tool: str
    params: Dict[str, Any]
    description: str
    depends_on: Optional[int] = None

    def __post_init__(self):
        self.agent = AgentType(self.agent)


@dataclass
class ExecutionPlan:
    steps: List[PlanStep]
    summary: str


class Orchestrator:
    def __init__(self, llm_service):
        self.llm_service = llm_service
        self.tools_by_agent = {a.type: a.tools for a in AGENTS.values()}
        self.agent_descriptions = {a.type: a.description for a in AGENTS.values()}

    def get_all_tools_context(self) -> str:
        lines = []
        for agent_type, agent in AGENTS.items():
            lines.append(f"\n{agent.name} Agent ({agent.type.value}): {agent.description}")
            for tool in agent.tools:
                lines.append(f"  - {tool.name}: {tool.description} [endpoint: {tool.endpoint}, params: {tool.params_schema}]")
        return "\n".join(lines)

    async def plan(self, user_message: str, conversation_history: List[Dict] = None) -> ExecutionPlan:
        tools_context = self.get_all_tools_context()
        
        system_prompt = f"""You are an agent orchestrator. Output ONLY valid JSON matching this exact schema:

{{
  "steps": [
    {{"agent": "runner|root|builder|llm", "tool": "tool_name", "params": {{"key": "value"}}, "description": "what this step does", "depends_on": 0}},
    ...
  ],
  "summary": "brief summary of the overall plan"
}}

Available agents and tools:
{tools_context}

Rules:
- agent must be one of: "llm", "root", "runner", "builder"
- tool must be a valid tool name from the list above
- params must match the tool's params_schema
- depends_on is optional integer index of previous step
- NO markdown, NO code fences, NO extra text, NO function_calls wrapper
- Chain steps logically (query_crm -> execute_python -> create_chart -> generate_pdf)

Example:
{{
  "steps": [
    {{"agent": "runner", "tool": "query_crm", "params": {{"query": "SELECT name, amount FROM deal"}}, "description": "Fetch deal data"}},
    {{"agent": "runner", "tool": "execute_python", "params": {{"code": "import pandas as pd\\ndf = pd.DataFrame(data)\\nprint(df.groupby(\"stage\")[\"amount\"].sum())"}}, "description": "Analyze pipeline by stage", "depends_on": 0}},
    {{"agent": "runner", "tool": "create_chart", "params": {{"code": "import pandas as pd\\nimport matplotlib.pyplot as plt\\ndf = pd.DataFrame(data)\\nplt.bar(df[\"stage\"], df[\"amount\"])\\nplt.title(\"Pipeline by Stage\")"}}, "description": "Create pipeline chart", "depends_on": 1}},
    {{"agent": "runner", "tool": "generate_pdf", "params": {{"content": \"Sales report generated\", "title\": \"Q3 Report\"}}, "description": "Generate PDF report", "depends_on": 2}}
  ],
  "summary": "Generate quarterly sales report with charts"
}}

User request: {user_message}
"""

        messages = [
            {"role": "system", "content": system_prompt},
            *(conversation_history or []),
            {"role": "user", "content": user_message}
        ]
        
        response = await self.llm_service.chat(messages, temperature=0.1)
        
        # Extract JSON from response (handle markdown code fences)
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()
        
        try:
            plan_data = json.loads(content)
            steps = [PlanStep(**s) for s in plan_data.get("steps", [])]
            if not self._is_plan_compatible(user_message, steps):
                return self._fallback_plan(user_message)
            return ExecutionPlan(steps=steps, summary=plan_data.get("summary", ""))
        except Exception as e:
            # Fallback to simple plan
            return self._fallback_plan(user_message)

    def _is_plan_compatible(self, user_message: str, steps: List[PlanStep]) -> bool:
        valid_tools = {
            agent: {tool.name for tool in tools}
            for agent, tools in self.tools_by_agent.items()
        }
        if any(step.tool not in valid_tools.get(step.agent, set()) for step in steps):
            return False

        analytics_terms = ["report", "pdf", "presentation", "chart", "graph", "plot", "visualize"]
        if any(term in user_message.lower() for term in analytics_terms):
            return all(step.agent == AgentType.RUNNER for step in steps)

        return True

    def _fallback_plan(self, user_message: str) -> ExecutionPlan:
        msg = user_message.lower()
        if any(kw in msg for kw in ["chart", "graph", "plot", "visualize"]):
            return ExecutionPlan(
                steps=[
                    PlanStep(AgentType.RUNNER, "query_crm", {"query": "SELECT stage, amount FROM deal"}, "Fetch deal data"),
                    PlanStep(AgentType.RUNNER, "create_chart", {"code": "import pandas as pd; import matplotlib.pyplot as plt; import seaborn as sns; df = pd.DataFrame(data); sns.barplot(data=df, x='stage', y='amount'); plt.title('Pipeline by Stage')"}, "Create pipeline chart", 0),
                ],
                summary="Create chart from CRM data"
            )
        elif any(kw in msg for kw in ["report", "pdf", "presentation"]):
            return ExecutionPlan(
                steps=[
                    PlanStep(AgentType.RUNNER, "query_crm", {"query": "SELECT * FROM deal"}, "Fetch all deals"),
                    PlanStep(AgentType.RUNNER, "execute_python", {"code": "import pandas as pd; df = pd.DataFrame(data); print(df.to_string())"}, "Format data for report", 0),
                    PlanStep(AgentType.RUNNER, "generate_pdf", {"content": "Sales report generated from CRM data", "title": "Sales Report"}, "Generate PDF", 1),
                ],
                summary="Generate PDF report"
            )
        else:
            return ExecutionPlan(steps=[], summary="General conversation")

    async def execute(self, plan: ExecutionPlan, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        results = {}

        class _InputObj:
            def __init__(self, params):
                for k, v in params.items():
                    setattr(self, k, v)
            def __getattr__(self, name):
                return None

        for i, step in enumerate(plan.steps):
            dep_result = results.get(step.depends_on) if step.depends_on is not None else None

            params = dict(step.params)
            if dep_result and dep_result.get("success"):
                if "code" in params:
                    import tempfile as _tf
                    rows = dep_result.get("rows", dep_result)
                    if isinstance(rows, list):
                        data_str = json.dumps(rows)
                    else:
                        data_str = json.dumps(dep_result)
                    params["code"] = f"data = {data_str}\n{params['code']}"

            try:
                if step.agent == AgentType.RUNNER:
                    from app.agent.agents.runner.tools import RunnerAgentTools
                    tools = RunnerAgentTools()
                    method = getattr(tools, step.tool)
                    result = method(_InputObj(params))
                elif step.agent == AgentType.ROOT:
                    from app.agent.agents.root.tools import RootAgentTools
                    tools = RootAgentTools()
                    method = getattr(tools, step.tool)
                    result = method(_InputObj(params))
                elif step.agent == AgentType.BUILDER:
                    from app.agent.agents.builder.tools import BuilderAgentTools
                    tools = BuilderAgentTools()
                    method = getattr(tools, step.tool)
                    result = method(_InputObj(params))
                elif step.agent == AgentType.LLM:
                    llm = self.llm_service
                    result = await llm.chat([{"role": "user", "content": step.params.get("prompt", "")}])
                    result = {"content": result.content, "error": result.error}
                else:
                    result = {"error": f"Unknown agent: {step.agent}"}

                if inspect.isawaitable(result):
                    result = await result

                results[i] = result

            except Exception as e:
                results[i] = {"error": str(e)}

        return {
            "plan_summary": plan.summary,
            "steps_executed": len(plan.steps),
            "results": results,
            "final_output": results.get(len(plan.steps) - 1, {}) if plan.steps else {}
        }


orchestrator = None

def get_orchestrator(llm_service=None):
    global orchestrator
    if orchestrator is None:
        from app.agent.llm import get_llm_service
        orchestrator = Orchestrator(llm_service or get_llm_service())
    return orchestrator