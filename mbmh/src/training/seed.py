from transformers import set_seed as hf_set_seed

def set_seed(seed: int):
    hf_set_seed(seed)
