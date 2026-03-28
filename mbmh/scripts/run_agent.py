#!/usr/bin/env python3
"""
Run a local agent from the command line.

Usage:
    python scripts/run_agent.py \
        --agent base-agent \
        --input "Summarise the contents of /tmp/notes.txt"
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.task_router import load_agents, get_agent
from src.agents.executor import agent_loop
from src.agents.memory import SessionMemory
from src.runtime.session_store import SessionStore


def _stub_generate(messages, *, temperature=0.7, max_tokens=256, stream=False):
    """Placeholder generate function when no model is loaded."""
    user_msg = ""
    for m in reversed(messages):
        if m["role"] == "user":
            user_msg = m["content"]
            break
    return f"[stub] Received: {user_msg}"


def main():
    parser = argparse.ArgumentParser(description="Run a local agent")
    parser.add_argument("--agent", type=str, required=True,
                        help="Agent config name (e.g. base-agent)")
    parser.add_argument("--agents-dir", type=str, default="configs/agents",
                        help="Directory containing agent YAML configs")
    parser.add_argument("--input", type=str, required=True,
                        help="The task/input to send to the agent")
    parser.add_argument("--bundle", type=str, default="latest",
                        help="Runtime bundle to use")
    args = parser.parse_args()

    # Load agents
    load_agents(args.agents_dir)
    agent = get_agent(args.agent)

    print(f"Agent loaded: {agent}")
    print(f"Input: {args.input}")
    print("-" * 60)

    messages = [{"role": "user", "content": args.input}]

    result = agent_loop(
        agent=agent,
        messages=messages,
        generate_fn=_stub_generate,
        tools={},
        safety_check=None,
    )

    print(f"Status: {result.status}")
    print(f"Iterations: {result.iterations}")
    print(f"Output:\n{result.output}")
    print("-" * 60)
    print(f"Trace ({len(result.trace)} entries):")
    for entry in result.trace:
        print(f"  [{entry['iteration']}] {entry['type']}: {str(entry.get('content', ''))[:120]}")

    # Persist
    store = SessionStore()
    memory = SessionMemory(store)
    memory.save_session(
        session_id=result.session_id,
        agent_name=args.agent,
        bundle_id=args.bundle,
        input_messages=messages,
        tool_trace=result.trace,
        final_output=result.output,
    )
    print(f"\nSession saved: {result.session_id}")


if __name__ == "__main__":
    main()
