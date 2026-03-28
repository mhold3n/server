from peft import LoraConfig, get_peft_model
from typing import Dict, Any

def apply_peft(model, config, registry_info: Dict[str, Any]):
    if not config.peft.use_peft:
        return model
        
    if config.peft.peft_type == "lora":
        target_modules = config.peft.target_modules or registry_info["default_lora_target_modules"]
        peft_config = LoraConfig(
            r=config.peft.r,
            lora_alpha=config.peft.lora_alpha,
            lora_dropout=config.peft.lora_dropout,
            bias=config.peft.bias,
            task_type=config.peft.task_type,
            target_modules=target_modules
        )
        return get_peft_model(model, peft_config)
    else:
        raise NotImplementedError(f"PEFT type {config.peft.peft_type} not implemented")
