import numpy as np
import pandas as pd

from backend.ml.sparkov_features import FEATURES, NUMERIC, batch_features, online_features


def rows():
    return [dict(customer_id="A",timestamp=t,amount=a,merchant=m,category="food",home_lat=40.,home_lon=-74.,merchant_lat=41.,merchant_lon=-73.)
            for t,a,m in [(100000,10,"M1"),(100000,99,"M2"),(101000,30,"M1"),(190000,80,"M3")]]


def test_batch_online_parity_and_strict_timestamp():
    source = rows()
    batch = batch_features(pd.DataFrame(source))
    for index,row in enumerate(source):
        online = online_features(row,source)
        np.testing.assert_allclose(batch.iloc[index][NUMERIC].astype(float),online.iloc[0][NUMERIC].astype(float),equal_nan=True,rtol=1e-5)
    assert batch.iloc[0].history_count == batch.iloc[1].history_count == 0
    assert batch.iloc[2].history_count == 2


def test_other_customer_and_future_cannot_change_features():
    source=rows()
    payment=source[2]
    before=online_features(payment,source)
    after=online_features(payment,source+[dict(source[0],customer_id="B",amount=1e9),dict(source[3],amount=1e9)])
    pd.testing.assert_frame_equal(before,after)
    assert "label" not in FEATURES and "customer_id" not in FEATURES
