def is_safe_tool_request(agent_config, tool_name):
    if tool_name not in agent_config.get("tools_allowed", []):
        return False
    return True
