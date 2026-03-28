import logging

runtime_logger = logging.getLogger("runtime")

def log_trace(session_id, step, details):
    runtime_logger.info(f"[{session_id}] {step}: {details}")
