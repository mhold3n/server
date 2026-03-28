import evaluate
import numpy as np

def compute_metrics(eval_preds):
    metric = evaluate.load("accuracy")
    preds, labels = eval_preds
    preds = np.argmax(preds, axis=-1)
    return metric.compute(predictions=preds, references=labels)
