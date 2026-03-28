import sqlite3
import datetime

class SessionStore:
    def __init__(self, db_path="outputs/runtime_sessions.db"):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                agent_name TEXT,
                bundle_id TEXT,
                input TEXT,
                tool_trace TEXT,
                final_output TEXT,
                timestamp TEXT
            )
        ''')
        self.conn.commit()

    def record_session(self, session_id, agent_name, bundle_id, input_text, tool_trace, final_output):
        self.cursor.execute('''
            INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (session_id, agent_name, bundle_id, input_text, tool_trace, final_output, datetime.datetime.now().isoformat()))
        self.conn.commit()
