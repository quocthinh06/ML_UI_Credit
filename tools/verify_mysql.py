"""Run the complete import → inference → MySQL → export path with synthetic IDs.

Creates a dedicated verification dataset and removes ONLY its own rows on completion.
No existing dataset or database is dropped.
"""

import json
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from sqlalchemy import delete, select

from creditrisk.config import ROOT, load_config, database_engine
from creditrisk.database import initialize, datasets, versions, records, runs, predictions
from creditrisk.inference import ModelRunner
from creditrisk.service import CreditService, read_file, export_frame
from creditrisk.validation import Thresholds


def main():
    engine = database_engine(load_config())
    initialize(engine)
    service = CreditService(engine)
    model = ModelRunner(ROOT / "models/best_model_v1.pkl")
    example = read_file(ROOT / "examples/sample_customers.csv")
    frame = pd.concat([example] * 3334, ignore_index=True).iloc[:10000].copy()
    frame["ID"] = [f"CHECK-{i:05d}" for i in range(len(frame))]
    did = None
    try:
        start = time.perf_counter()
        vid = service.import_dataset("AUTOMATED VERIFICATION - synthetic records", frame)
        with engine.connect() as conn:
            did = conn.scalar(select(versions.c.dataset_id).where(versions.c.id == vid))
        rid, output = service.predict_version(vid, model, Thresholds())
        elapsed = time.perf_counter() - start
        saved = service.results(rid)
        assert len(saved) == len(frame)
        assert saved["default_label"].tolist() == output["default_label"].tolist()
        assert abs(saved.iloc[0]["probability"] - 0.040737) < 0.000005
        changed = frame.iloc[0].drop("ID").to_dict()
        changed["AGE"] = 41
        v2 = service.revise_dataset(did, "CHECK-00000", changed, replace=True, expected_version=vid)
        assert service.data(vid).iloc[0]["AGE"] == 35
        assert service.data(v2).iloc[0]["AGE"] == 41
        assert len(service.results(rid)) == 10000
        portfolio = service.portfolio()
        assert (portfolio.loc[portfolio.dataset_id == did, "status"] == "Cần dự báo lại").all()
        with tempfile.TemporaryDirectory() as temp:
            export_frame(saved, Path(temp) / "results.xlsx")
            assert len(pd.read_excel(Path(temp) / "results.xlsx")) == 10000
        print(
            json.dumps(
                {
                    "mysql": "PASS",
                    "records": 10000,
                    "import_predict_persist_seconds": round(elapsed, 3),
                    "revision_history": "PASS",
                    "xlsx_export": "PASS",
                },
                indent=2,
            )
        )
    finally:
        if did is not None:
            with engine.begin() as conn:
                vids = select(versions.c.id).where(versions.c.dataset_id == did)
                rids = select(runs.c.id).where(runs.c.version_id.in_(vids))
                conn.execute(delete(predictions).where(predictions.c.run_id.in_(rids)))
                conn.execute(delete(runs).where(runs.c.version_id.in_(vids)))
                conn.execute(delete(records).where(records.c.version_id.in_(vids)))
                conn.execute(delete(versions).where(versions.c.dataset_id == did))
                conn.execute(delete(datasets).where(datasets.c.id == did))
        engine.dispose()


if __name__ == "__main__":
    main()
