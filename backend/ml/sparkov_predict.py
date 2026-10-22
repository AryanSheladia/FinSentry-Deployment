import joblib
import numpy as np

from backend.ml.sparkov_train import ARTIFACTS, calibrated
from backend.ml.sparkov_features import online_features


class SparkovPredictor:
    def __init__(self):
        self.bundle=joblib.load(ARTIFACTS/"pipeline.joblib")
        self.metadata=self.bundle["metadata"]

    def predict(self,payment,history):
        features=online_features(payment,history)
        raw=self.bundle["model"].predict_proba(self.bundle["preprocess"].transform(features))[:,1]
        score=float(calibrated(raw,self.bundle["calibrator"])[0])
        if not np.isfinite(score):
            raise ValueError("Invalid model score")
        snapshot={k:None if isinstance(v,(float,np.floating)) and np.isnan(v) else v for k,v in features.iloc[0].to_dict().items()}
        return {"risk_score":score,"threshold":self.metadata["threshold"],"model_flag":score>=self.metadata["threshold"],
                "score_type":self.metadata["score_type"],"model_version":self.metadata["model_version"],"features":snapshot}
