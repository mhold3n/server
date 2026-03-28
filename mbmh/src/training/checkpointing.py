
def save_checkpoint(trainer, config_snapshot, output_dir):
    trainer.save_model(output_dir)
    # Save config mapping as well
