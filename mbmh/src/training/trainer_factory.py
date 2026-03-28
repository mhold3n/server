from trl import SFTTrainer
from transformers import Trainer, TrainingArguments

def create_trainer(model, tokenizer, config, dataset, collator, task="sft"):
    
    args = TrainingArguments(
        output_dir=config.training.output_dir,
        logging_dir=config.training.logging_dir,
        max_steps=config.training.max_steps,
        save_strategy=config.training.save_strategy,
        evaluation_strategy=config.training.eval_strategy,
        gradient_checkpointing=config.training.gradient_checkpointing,
        fp16=config.device.fp16,
        bf16=config.device.bf16,
        report_to=config.training.report_to,
        seed=config.training.seed,
        per_device_train_batch_size=config.device.per_device_train_batch_size,
        per_device_eval_batch_size=config.device.per_device_eval_batch_size,
        dataloader_num_workers=config.device.dataloader_num_workers
    )

    if task == "sft":
        trainer = SFTTrainer(
            model=model,
            args=args,
            train_dataset=dataset.get("train"),
            eval_dataset=dataset.get("test"),
            tokenizer=tokenizer,
            data_collator=collator,
            dataset_text_field=config.training.dataset_text_field,
            packing=config.training.packing
        )
    elif task == "clm":
        trainer = Trainer(
            model=model,
            args=args,
            train_dataset=dataset.get("train"),
            eval_dataset=dataset.get("test"),
            tokenizer=tokenizer,
            data_collator=collator
        )
    else:
        raise ValueError(f"Unknown task {task}")
        
    return trainer
