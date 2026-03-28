import os
import yaml
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field

class PeftConfig(BaseModel):
    use_peft: bool = False
    peft_type: str = "lora"
    r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    target_modules: Optional[Union[List[str], str]] = None
    bias: str = "none"
    task_type: str = "CAUSAL_LM"

class DistributedConfig(BaseModel):
    distributed: bool = False
    fsdp_enabled: bool = False
    fsdp_config: Optional[Dict[str, Any]] = None

class DeviceConfig(BaseModel):
    device_preference: str = "cpu"
    per_device_train_batch_size: int = 1
    per_device_eval_batch_size: int = 1
    dataloader_num_workers: int = 0
    fp16: bool = False
    bf16: bool = False

class ModelConfig(BaseModel):
    family: str
    base_model: str
    tokenizer: str
    model_type: str = "causal_lm"
    max_context: int = 4096
    chat_template_mode: str = "default"
    default_lora_target_modules: Optional[List[str]] = None
    supported_tasks: List[str] = ["sft"]
    allow_full_finetune: bool = False

class TrainingConfig(BaseModel):
    seed: int = 42
    output_dir: str = "outputs/runs"
    logging_dir: str = "logs"
    max_steps: int = 1000
    save_strategy: str = "steps"
    eval_strategy: str = "steps"
    gradient_checkpointing: bool = False
    report_to: str = "none"
    task_type: str = "base"
    strict_validation: bool = True
    packing: bool = False
    dataset_text_field: Optional[str] = None
    metrics: Optional[List[str]] = None

class AppConfig(BaseModel):
    training: TrainingConfig = Field(default_factory=TrainingConfig)
    model: Optional[ModelConfig] = None
    device: DeviceConfig = Field(default_factory=DeviceConfig)
    peft: PeftConfig = Field(default_factory=PeftConfig)
    dist: DistributedConfig = Field(default_factory=DistributedConfig)

def deep_update(target: dict, source: dict) -> dict:
    for k, v in source.items():
        if isinstance(v, dict) and k in target and isinstance(target[k], dict):
            target[k] = deep_update(target[k], v)
        else:
            target[k] = v
    return target

def load_yaml(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, 'r') as f:
        return yaml.safe_load(f) or {}

def load_and_merge_config(*yaml_paths: str) -> AppConfig:
    merged_data = {}
    for path in yaml_paths:
        data = load_yaml(path)
        # Assuming flattened configs for simplicity right now,
        # but structured ideally into model, training, peft etc.
        merged_data = deep_update(merged_data, data)
    
    # Simple mapping heuristic mapping flat yaml fields to nested categories
    training_fields = TrainingConfig.model_fields.keys()
    device_fields = DeviceConfig.model_fields.keys()
    model_fields = ModelConfig.model_fields.keys()
    peft_fields = PeftConfig.model_fields.keys()
    dist_fields = DistributedConfig.model_fields.keys()

    nested_kwargs = {
        "training": {},
        "model": {},
        "device": {},
        "peft": {},
        "dist": {}
    }

    for k, v in merged_data.items():
        if k in training_fields:
            nested_kwargs["training"][k] = v
        elif k in device_fields:
            nested_kwargs["device"][k] = v
        elif k in model_fields:
            nested_kwargs["model"][k] = v
        elif k in peft_fields:
            nested_kwargs["peft"][k] = v
        elif k in dist_fields:
            nested_kwargs["dist"][k] = v

    if not nested_kwargs["model"]:
        nested_kwargs["model"] = None

    return AppConfig(**nested_kwargs)
