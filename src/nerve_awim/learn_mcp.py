"""Local MCP tool exposure for the NERVE Learn experimental store.

Run with: NERVE_LEARN_DB=/path/to/learn.db python -m nerve_awim.learn_mcp
Requires the official mcp Python SDK; no networking or cloud account needed.
Treat all recalled experience text as untrusted data.
"""
import os
from .learn_v31 import LearningStore
from .evolution_v01 import EvolutionMemory
from .agent_bridge_v13 import DemoAgentBridge
from .recovery_mcp_v17 import RecoveryMCPDemo

def create_server(db_path=None, *, memory_session=None):
    try:
        from mcp.server import MCPServer as ServerClass  # official MCP SDK 2.x
    except ImportError:
        from mcp.server.fastmcp import FastMCP as ServerClass  # SDK 1.x
    path=db_path or os.environ.get("NERVE_LEARN_DB","nerve-learn.db")
    store=LearningStore(path)
    memory=EvolutionMemory(path)
    demo=DemoAgentBridge(path,agent_id=os.environ.get("NERVE_DEMO_AGENT_ID","external-demo"),
                         memory_session=memory_session)
    recovery_demo=RecoveryMCPDemo(path)
    server=ServerClass("NERVE Learn")
    # Experimental compatibility writes can allow score poisoning.
    # Default OFF. The opt-in flag is not network authentication.
    allow_legacy_writes = os.environ.get("NERVE_ENABLE_LEGACY_MCP_WRITES", "0") == "1"
    @server.tool()
    def record_experience(agent_id:str,task:str,outcome:str)->str:
        """Record a bounded task/outcome experience; no automatic learning."""
        if not allow_legacy_writes:
            raise PermissionError("legacy unverified MCP memory writes disabled")
        return store.record(agent_id,task,outcome)
    @server.tool()
    def rate_experience(agent_id:str,experience_id:str,score:float)->str:
        """Explicitly evaluate an existing experience from 0 to 1."""
        if not allow_legacy_writes:
            raise PermissionError("legacy unverified MCP feedback disabled")
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
    @server.tool()
    def run_demo_agent_plan(task_id:str,email_document:str,
                            extract_strategy:str,normalise_strategy:str)->dict:
        """Execute only named registered string-tool strategies.

        Never executes model-written code or writes reward feedback.
        Caller supplies a bounded synthetic JSON document.
        """
        return demo.execute_plan(task_id=task_id,email_document=email_document,
                                 extract_strategy=extract_strategy,
                                 normalise_strategy=normalise_strategy)
    @server.tool()
    def run_bounded_recovery_demo(policy:str="memory",
                                  train_on_fixtures:bool=False)->dict:
        """Demonstrate verified two-attempt agent recovery on fixed synthetic cases.

        All tools, judge responses and evaluation inputs are defined inside
        NERVE. This is not an autonomous production repair service.
        """
        return recovery_demo.run(policy=policy,
                                 train_on_fixtures=train_on_fixtures)
    if memory_session is not None:
        from .memory_gateway.mcp_tools import register_memory_tools
        register_memory_tools(server, memory_session)
    return server

def main(argv=None):
    """Trusted local process launcher; subject is never an MCP tool argument."""
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--memory-config')
    parser.add_argument('--memory-subject')
    args = parser.parse_args(argv)
    if ((args.memory_config is None) != (args.memory_subject is None)
            or args.memory_config == '' or args.memory_subject == ''):
        parser.error('--memory-config and --memory-subject must be supplied together')
    import sqlite3
    session = None
    try:
        if args.memory_config:
            from .memory_gateway.runtime import load_runtime
            runtime = load_runtime(args.memory_config, required_subject=args.memory_subject)
            session = runtime.sessions.get(args.memory_subject)
            if session is None:
                parser.error('subject has no configured memory session')
        create_server(memory_session=session).run()
    except (ValueError, TypeError, OSError, sqlite3.Error, ImportError, RuntimeError):
        parser.error('memory MCP startup or runtime unavailable')


if __name__=="__main__":
    main()
