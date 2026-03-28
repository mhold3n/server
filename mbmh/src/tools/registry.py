
TOOL_REGISTRY = {}

def register_tool(name: str):
    def wrapper(cls):
        TOOL_REGISTRY[name] = cls
        return cls
    return wrapper

def get_enabled_tools(allowed_names: list, config: dict):
    instances = {}
    for name in allowed_names:
        if name in TOOL_REGISTRY:
            # Look up specific tool config
            tool_cfg = config.get("tools", {}).get(name, {})
            if tool_cfg.get("enabled", False):
                instances[name] = TOOL_REGISTRY[name](**tool_cfg)
    return instances
