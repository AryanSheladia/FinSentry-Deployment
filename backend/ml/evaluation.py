"""Dataset-independent evaluation and artifact helpers."""
import hashlib
import json
import numpy as np
from sklearn.metrics import (average_precision_score,confusion_matrix,f1_score,precision_recall_curve,
                             precision_score,recall_score,roc_auc_score)


def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+"\n",encoding="utf-8")


def sha256(path):
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):
            digest.update(chunk)
    return digest.hexdigest()


def select_threshold(labels,scores):
    precision,recall,thresholds=precision_recall_curve(labels,scores)
    if not len(thresholds):
        raise ValueError("No usable validation thresholds")
    denom=precision[:-1]+recall[:-1]
    f1=np.divide(2*precision[:-1]*recall[:-1],denom,out=np.zeros_like(denom),where=denom!=0)
    return float(thresholds[int(np.argmax(f1))])


def evaluate(labels,scores,threshold):
    predictions=scores>=threshold
    return {"average_precision":float(average_precision_score(labels,scores)),"roc_auc":float(roc_auc_score(labels,scores)),
            "precision":float(precision_score(labels,predictions,zero_division=0)),"recall":float(recall_score(labels,predictions,zero_division=0)),
            "f1":float(f1_score(labels,predictions,zero_division=0)),"review_rate":float(predictions.mean()),
            "confusion_matrix":confusion_matrix(labels,predictions,labels=[0,1]).tolist()}
