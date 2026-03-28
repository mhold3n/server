import os
import json

def resolve_bundle(bundle_id: str):
    bundle_path = os.path.join("outputs", "packaged", "runtime-bundles", bundle_id)
    manifest_path = os.path.join(bundle_path, "artifact_manifest.json")
    
    if not os.path.exists(manifest_path):
        raise ValueError(f"Bundle {bundle_id} not found or missing manifest")
        
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)
        
    return bundle_path, manifest
