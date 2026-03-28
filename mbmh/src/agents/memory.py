"""
Session memory backed by the SQLite session store.
"""

import json
from typing import List, Dict, Optional

from ..runtime.session_store import SessionStore


class SessionMemory:
    """Provides get/append over the SQLite session store for agent turns."""

    def __init__(self, store: SessionStore):
        self.store = store

    def save_session(
        self,
        session_id: str,
        agent_name: str,
        bundle_id: str,
        input_messages: List[Dict[str, str]],
        tool_trace: list,
        final_output: str,
    ):
        """Persist a completed agent session."""
        self.store.record_session(
            session_id=session_id,
            agent_name=agent_name,
            bundle_id=bundle_id,
            input_text=json.dumps(input_messages),
            tool_trace=json.dumps(tool_trace),
            final_output=final_output,
        )

    def get_session(self, session_id: str) -> Optional[Dict]:
        """Retrieve a session by ID. Returns None if not found."""
        self.store.cursor.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        )
        row = self.store.cursor.fetchone()
        if row is None:
            return None
        return {
            "session_id": row[0],
            "agent_name": row[1],
            "bundle_id": row[2],
            "input": json.loads(row[3]) if row[3] else [],
            "tool_trace": json.loads(row[4]) if row[4] else [],
            "final_output": row[5],
            "timestamp": row[6],
        }
