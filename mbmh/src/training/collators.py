from transformers import DataCollatorForLanguageModeling

def get_collator(config, tokenizer, task="sft"):
    if task == "sft":
        # Simplified: fallback to default if packing is enabled
        return DataCollatorForLanguageModeling(tokenizer, mlm=False)
    elif task == "clm":
        return DataCollatorForLanguageModeling(tokenizer, mlm=False)
    return None
