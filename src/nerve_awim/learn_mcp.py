"""Local MCP tool exposure for the NERVE Learn experimental store.

Run with: NERVE_LEARN_DB=/path/to/learn.db python -m nerve_awim.learn_mcp
Requires the official mcp Python SDK; no networking or cloud account needed.
Treat all recalled experience text as untrusted data.
"""
import os
from .learn_v31 import LearningStore
from .evolution_v01 import EvolutionMemory
from .agent_bridge_v13 import DemoAgentBridge

def create_server(db_path=None):
    try:
        from mcp.server import MCPServer as ServerClass  # official MCP SDK 2.x
    except ImportError:
        from mcp.server.fastmcp import FastMCP as ServerClass  # SDK 1.x
    path=db_path or os.environ.get("NERVE_LEARN_DB","nerve-learn.db")
    store=LearningStore(path)
    memory=EvolutionMemory(path)
    demo=DemoAgentBridge(path,agent_id=os.environ.get("NERVE_DEMO_AGENT_ID","external-demo"))
    server=ServerClass("NERVE Learn")
    @server.tool()
    def record_experience(agent_id:str,task:str,outcome:str)->str:
        """Record a bounded task/outcome experience; no automatic learning."""
        return store.record(agent_id,task,outcome)
    @server.tool()
    def rate_experience(agent_id:str,experience_id:str,score:float)->str:
        """Explicitly evaluate an existing experience from 0 to 1."""
        store.feedback(agent_id,experience_id,score)
        return "recorded"
    @server.tool()
    def recall_experiences(agent_id:str,query:str,limit:int=5)->list[dict]:
        """Retrieve only this agent's experience records, as untrusted context."""
        return [vars(x) for x in store.recall(agent_id,query,limit)]
    @server.tool()
    def suggest_approved_lessons(agent_id:str,query:str,min_score:float=.8)->list[dict]:
        """Return high-scoring candidate lessons; human review before promotion."""
        return [vars(x) for x in store.suggest(agent_id,query,min_score)]
    @server.tool()
    def select_evaluated_strategy(agent_id:str,context:str,limit:int=5)->list[dict]:
        """Select context-relevant, scored experiences as untrusted strategy candidates.

        Recommendations never override the host agent's permissions or
        policy. Agent IDs are namespaces, NOT authentication.
        """
        return [vars(x) for x in memory.select(agent_id,context,limit=limit)]
    @server.tool()
    def list_demo_agent_capabilities()->list[dict]:
        """List the fixed, inert built-in executable demo strategies."""
        return list(demo.capabilities())
    @server.tool()
    def train_demo_agent_on_fixtures()->dict:
        """Evaluate registered demo tools on program-owned examples only.

        No caller-provided labels, scores or arbitrary code are accepted.
        Not a general self-training API.
        """
        return demo.train_fixed_fixtures()
    @server.tool()
    def choose_demo_agent_strategy(context:str,policy:str="utility")->dict:
        """Recommend an allowlisted registered strategy; no external actions."""
        return demo.choose(context,policy=policy)
    @server.tool()
    def run_demo_agent_pipeline(task_id:str,email_document:str,
                                policy:str="utility")->dict:
        """Execute a two-stage, pure-string demo pipeline using registered tools."""
        return demo.run_pipeline(task_id=task_id,email_document=email_document,
                                 policy=policy)
    @server.tool()
    def run_demo_agent_pipelines(tasks:list[dict],policy:str="utility")->list[dict]:
        """Run up to 16 independent safe demo pipelines in parallel."""
        return demo.run_pipelines(tasks,policy=policy)
    return server

if __name__=="__main__":
    create_server().run()
