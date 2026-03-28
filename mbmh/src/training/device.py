import torch

def detect_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        return "mps"
    return "cpu"

def validate_device_capabilities(config_device: str, strict_validation: bool = True) -> str:
    actual_device = detect_device()
    
    # 1. explicit valid config
    if config_device == "cuda":
        if not torch.cuda.is_available():
            msg = "CUDA requested but not available."
            if strict_validation:
                raise RuntimeError(msg)
            print(f"WARNING: {msg} Falling back to {actual_device}")
            return actual_device
        return "cuda"

    if config_device == "mps":
        if not (hasattr(torch.backends, 'mps') and torch.backends.mps.is_available()):
            msg = "MPS requested but not available."
            if strict_validation:
                raise RuntimeError(msg)
            print(f"WARNING: {msg} Falling back to {actual_device}")
            return actual_device
        return "mps"

    if config_device == "cpu":
        return "cpu"
        
    return actual_device

def is_distributed_allowed(device: str, config):
    if device == "mps":
        if config.dist.distributed:
            print("WARNING: Distributed training is forbidden on MPS. Disabling distributed.")
            return False
    if device == "cpu" and config.dist.distributed:
         print("WARNING: Distributed generally not supported correctly on CPU via this script defaults. Disabling.")
         return False
    
    if config.device.bf16 and device == "mps":
        print("WARNING: BF16 on MPS isn't uniformly supported. Proceeding with caution.")
    
    return config.dist.distributed

def get_device(config, strict_validation: bool = True) -> str:
    pref_device = config.device.device_preference
    validated_device = validate_device_capabilities(pref_device, strict_validation)
    return validated_device
