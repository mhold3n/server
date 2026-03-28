def map_runtime_to_openclaw(runtime_payload):
    # Map from local schema to consumer schema
    return {"choices": [{"message": {"content": runtime_payload.get("text", "")}}]}
