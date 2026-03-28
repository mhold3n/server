from datasets import load_dataset
import logging

logger = logging.getLogger(__name__)

def load_and_validate_dataset(config, task="sft"):
    # Mocking actual load
    # user logic specifies dataset requirements
    dataset = load_dataset("json", data_files={"train": config.data.train_file})
    # Valdiation depending on task
    if task == "sft":
        if "messages" not in dataset["train"].column_names:
            logger.warning("Dataset missing 'messages', expecting SFT format")
    elif task == "clm":
        if "text" not in dataset["train"].column_names:
            logger.warning("Dataset missing 'text', expecting CLM format")
    return dataset
