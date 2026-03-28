from transformers import AutoModelForCausalLM
import torch

def load_base_model(config, device: str):
    kwargs = {}
    if config.device.fp16:
        kwargs["torch_dtype"] = torch.float16
    elif config.device.bf16:
        kwargs["torch_dtype"] = torch.bfloat16
        
    if config.training.gradient_checkpointing:
        kwargs["use_cache"] = False
        
    model = AutoModelForCausalLM.from_pretrained(config.model.base_model, **kwargs)
    
    if config.training.gradient_checkpointing:
        model.gradient_checkpointing_enable()
        
    return model
