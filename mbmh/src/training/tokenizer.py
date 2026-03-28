from transformers import AutoTokenizer

def load_tokenizer(config):
    tokenizer = AutoTokenizer.from_pretrained(config.model.tokenizer)
    # Apply chat templates heuristics if needed
    if config.model.chat_template_mode == "chatml":
        pass # Add specific chatml template if tokenizer lacks it
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    return tokenizer
