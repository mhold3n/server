#!/usr/bin/env python3
from src.training.config import load_and_merge_config
from src.training.device import get_device
from src.training.registry import validate_family
from src.training.logging import setup_logging
from src.training.seed import set_seed

def main():
    setup_logging()
    
    # Load configs
    # In a real run, parse yaml paths from argparse
    config = load_and_merge_config(
        "configs/base.yaml", 
        "configs/tasks/sft.yaml",
        "configs/models/llama.yaml" # defaults stub
    )
    
    set_seed(config.training.seed)
    get_device(config, strict_validation=config.training.strict_validation)
    
    validate_family(config.model.family)
    
    # Normally load_dataset here, skipping deep impl for skeleton
    
    print("SFT Training Script initialized successfully (Skeleton).")

    # Resume support and actual train loop omitted in skeleton...

if __name__ == "__main__":
    main()
