MODEL_REGISTRY = {
    "llama": {
        "family": "llama",
        "model_type": "causal_lm",
        "tokenizer_behavior": "default",
        "default_lora_target_modules": ["q_proj", "v_proj", "k_proj", "o_proj"],
        "supported_tasks": ["sft", "clm"],
        "max_tested_context": 4096,
        "allow_full_finetune": True,
    },
    "mistral": {
        "family": "mistral",
        "model_type": "causal_lm",
        "tokenizer_behavior": "default",
        "default_lora_target_modules": ["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        "supported_tasks": ["sft", "clm"],
        "max_tested_context": 8192,
        "allow_full_finetune": True,
    },
    "qwen": {
        "family": "qwen",
        "model_type": "causal_lm",
        "tokenizer_behavior": "chatml",
        "default_lora_target_modules": ["c_attn", "c_proj", "w1", "w2"],
        "supported_tasks": ["sft"],
        "max_tested_context": 32768,
        "allow_full_finetune": False,
    },
    "gemma": {
        "family": "gemma",
        "model_type": "causal_lm",
        "tokenizer_behavior": "default",
        "default_lora_target_modules": ["q_proj", "v_proj", "k_proj", "o_proj"],
        "supported_tasks": ["sft"],
        "max_tested_context": 8192,
        "allow_full_finetune": False,
    }
}

def validate_family(family: str):
    if family not in MODEL_REGISTRY:
        raise ValueError(f"Family {family} not supported. Allowed: {list(MODEL_REGISTRY.keys())}")
    return MODEL_REGISTRY[family]
