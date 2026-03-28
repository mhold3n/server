import os
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

def load_from_bundle(bundle_path, manifest):
    # Determine base model or merged model
    if "merged" in manifest.get("layers", []):
        model_path = os.path.join(bundle_path, "merged")
        model = AutoModelForCausalLM.from_pretrained(model_path)
    elif "adapter" in manifest.get("layers", []):
        base_id = manifest["base_model"]
        base_model = AutoModelForCausalLM.from_pretrained(base_id)
        adapter_path = os.path.join(bundle_path, "adapter")
        model = PeftModel.from_pretrained(base_model, adapter_path)
    else:
        raise ValueError("Unknown bundle structure")
        
    tokenizer_path = os.path.join(bundle_path, "tokenizer")
    if not os.path.exists(tokenizer_path):
        tokenizer_path = manifest["base_model"] # fallback
        
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_path)
    
    return model, tokenizer
