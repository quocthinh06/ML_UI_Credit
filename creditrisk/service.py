from dataclasses import asdict
from pathlib import Path
import os
import tempfile

import pandas as pd
from sqlalchemy import func, insert, select

from .database import datasets, versions, records, runs, predictions
from .validation import FEATURES, ValidationError, customer_ids, validate_frame


def read_file(path):
    path = Path(path)
    if path.suffix.lower() == ".csv":
        # Inspect the raw header: pandas otherwise silently renames duplicate columns.
        import csv

        with path.open(encoding="utf-8-sig", newline="") as stream:
            header = next(csv.reader(stream), [])
        stripped = [c.strip() for c in header]
        if len(stripped) != len(set(stripped)):
            raise ValidationError("Tệp chứa tên cột bị trùng.")
        frame = pd.read_csv(path, encoding="utf-8-sig", dtype={"ID": str})
    elif path.suffix.lower() == ".xlsx":
        header = pd.read_excel(path, header=None, nrows=1).iloc[0].map(str).str.strip()
        if header.duplicated().any():
            raise ValidationError("Tệp chứa tên cột bị trùng.")
        frame = pd.read_excel(path, dtype={"ID": str})
    else:
        raise ValidationError("Chỉ hỗ trợ CSV UTF-8 và Excel .xlsx.")
    frame.columns = [str(c).strip() for c in frame.columns]
    values = validate_frame(frame)
    values.insert(0, "ID", customer_ids(frame))
    return values


def export_frame(frame, path):
    """Write beside destination and replace only after the entire export succeeds."""
    path = Path(path)
    if path.suffix.lower() not in (".csv", ".xlsx"):
        raise ValidationError("Tên tệp xuất cần đuôi .csv hoặc .xlsx.")
    safe = frame.copy()
    # Spreadsheet formula injection: imported identifiers and dataset names are untrusted.
    for col in safe.select_dtypes(include=["object", "string"]).columns:
        safe[col] = safe[col].map(
            lambda x: "'" + x if isinstance(x, str) and x.lstrip().startswith(("=", "+", "-", "@")) else x
        )
    fd, name = tempfile.mkstemp(suffix=path.suffix, dir=path.parent)
    os.close(fd)
    try:
        if path.suffix.lower() == ".csv":
            safe.to_csv(name, index=False, encoding="utf-8-sig")
        else:
            safe.to_excel(name, index=False)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class CreditService:
    def __init__(self, engine):
        self.engine = engine

    def list_datasets(self):
        with self.engine.connect() as conn:
            return pd.read_sql(
                select(
                    datasets.c.id,
                    datasets.c.name,
                    datasets.c.created_at,
                    func.max(versions.c.revision).label("revision"),
                    func.max(versions.c.id).label("version_id"),
                )
                .join(versions)
                .group_by(datasets.c.id, datasets.c.name, datasets.c.created_at)
                .order_by(datasets.c.id.desc()),
                conn,
            )

    def save_single(
        self, frame, output, model, thresholds, *, dataset_id=None, replace=False, expected_version=None
    ):
        values = validate_frame(frame)
        ids = customer_ids(frame)
        if len(values) != 1 or len(output) != 1:
            raise ValidationError("Lưu đơn lẻ cần đúng một hồ sơ.")
        with self.engine.begin() as conn:
            if dataset_id is None:
                did = conn.execute(
                    insert(datasets).values(name=f"Hồ sơ {ids[0]}"[:255])
                ).inserted_primary_key[0]
                vid = self._write_version(conn, did, 1, values, ids)
            else:
                vid = self._revise(conn, dataset_id, ids[0], values, replace, expected_version)
            rid = conn.execute(
                select(records.c.id).where(records.c.version_id == vid, records.c.customer_id == ids[0])
            ).scalar_one()
            run_id = conn.execute(
                insert(runs).values(
                    version_id=vid,
                    model_name=model.name,
                    model_version=model.version,
                    model_hash=model.digest,
                    thresholds=asdict(thresholds),
                )
            ).inserted_primary_key[0]
            result = output[["raw_score", "probability", "default_label", "risk_level"]].iloc[0].to_dict()
            conn.execute(insert(predictions).values(run_id=run_id, record_id=rid, **result))
        return run_id

    def import_dataset(self, name, frame):
        values = validate_frame(frame)
        ids = customer_ids(frame)
        name = name.strip()
        if not name or len(name) > 255:
            raise ValidationError("Tên tệp phải có từ 1 đến 255 ký tự.")
        with self.engine.begin() as conn:
            dataset_id = conn.execute(insert(datasets).values(name=name)).inserted_primary_key[0]
            return self._write_version(conn, dataset_id, 1, values, ids)

    @staticmethod
    def _write_version(conn, dataset_id, revision, values, ids):
        vid = conn.execute(
            insert(versions).values(dataset_id=dataset_id, revision=revision)
        ).inserted_primary_key[0]
        rows = [
            {"version_id": vid, "customer_id": cid, "inputs": row}
            for cid, row in zip(ids, values.to_dict("records"))
        ]
        conn.execute(insert(records), rows)
        return vid

    def revise_dataset(self, dataset_id, customer_id, inputs, *, replace=False, expected_version=None):
        """Lock dataset to serialize revisions; explicit duplicate resolution only."""
        new = validate_frame(pd.DataFrame([inputs]))
        customer_id = str(customer_id).strip()
        if not customer_id or len(customer_id) > 128:
            raise ValidationError("ID phải có từ 1 đến 128 ký tự.")
        with self.engine.begin() as conn:
            return self._revise(conn, dataset_id, customer_id, new, replace, expected_version)

    def _revise(self, conn, dataset_id, customer_id, new, replace, expected_version):
        row = conn.execute(select(datasets).where(datasets.c.id == dataset_id).with_for_update()).first()
        if row is None:
            raise ValidationError("Không tìm thấy tệp dữ liệu.")
        latest = (
            conn.execute(
                select(versions)
                .where(versions.c.dataset_id == dataset_id)
                .order_by(versions.c.revision.desc())
                .limit(1)
            )
            .mappings()
            .one()
        )
        if expected_version is not None and latest["id"] != expected_version:
            raise ValidationError("Tệp đã có phiên bản mới. Hãy tải lại trước khi lưu.")
        current = pd.DataFrame(
            conn.execute(select(records).where(records.c.version_id == latest["id"])).mappings().all()
        )
        ids = current["customer_id"].tolist()
        values = pd.DataFrame(current["inputs"].tolist(), columns=FEATURES)
        if customer_id in ids:
            if not replace:
                raise ValidationError("ID đã tồn tại. Chọn cập nhật rõ ràng hoặc nhập ID khác.")
            values.loc[ids.index(customer_id)] = new.iloc[0]
        else:
            ids.append(customer_id)
            values = pd.concat([values, new], ignore_index=True)
        return self._write_version(conn, dataset_id, latest["revision"] + 1, values, ids)

    def data(self, version_id):
        with self.engine.connect() as conn:
            rows = (
                conn.execute(select(records).where(records.c.version_id == version_id).order_by(records.c.id))
                .mappings()
                .all()
            )
        if not rows:
            raise ValidationError("Phiên bản dữ liệu không tồn tại hoặc không có hồ sơ.")
        return pd.DataFrame([{"record_id": r["id"], "ID": r["customer_id"], **r["inputs"]} for r in rows])

    def version_history(self, dataset_id):
        with self.engine.connect() as conn:
            return pd.read_sql(
                select(versions)
                .where(versions.c.dataset_id == dataset_id)
                .order_by(versions.c.revision.desc()),
                conn,
            )

    def predict_version(self, version_id, model, thresholds):
        frame = self.data(version_id)
        result = model.predict(frame, thresholds)
        with self.engine.begin() as conn:
            run_id = conn.execute(
                insert(runs).values(
                    version_id=version_id,
                    model_name=model.name,
                    model_version=model.version,
                    model_hash=model.digest,
                    thresholds=asdict(thresholds),
                )
            ).inserted_primary_key[0]
            rows = [
                {"run_id": run_id, "record_id": int(rid), **row}
                for rid, row in zip(frame["record_id"], result.to_dict("records"))
            ]
            conn.execute(insert(predictions), rows)
        return run_id, pd.concat([frame, result], axis=1)

    def history(self):
        with self.engine.connect() as conn:
            return pd.read_sql(
                select(
                    runs.c.id.label("run_id"),
                    datasets.c.name,
                    versions.c.revision,
                    runs.c.version_id,
                    runs.c.model_name,
                    runs.c.model_version,
                    runs.c.created_at,
                    runs.c.thresholds,
                    runs.c.model_hash,
                )
                .join(versions, runs.c.version_id == versions.c.id)
                .join(datasets, versions.c.dataset_id == datasets.c.id)
                .order_by(runs.c.id.desc()),
                conn,
            )

    def results(self, run_id):
        with self.engine.connect() as conn:
            rows = (
                conn.execute(
                    select(
                        records.c.customer_id.label("ID"),
                        records.c.inputs,
                        predictions.c.raw_score,
                        predictions.c.probability,
                        predictions.c.default_label,
                        predictions.c.risk_level,
                    )
                    .join(predictions, records.c.id == predictions.c.record_id)
                    .where(predictions.c.run_id == run_id)
                    .order_by(records.c.id)
                )
                .mappings()
                .all()
            )
        return pd.DataFrame([{**r["inputs"], **{k: v for k, v in r.items() if k != "inputs"}} for r in rows])

    def portfolio(self):
        """Only latest versions and latest run per version; no double counting history."""
        latest_versions = (
            select(versions.c.dataset_id, func.max(versions.c.id).label("vid"))
            .group_by(versions.c.dataset_id)
            .subquery()
        )
        latest_runs = (
            select(runs.c.version_id, func.max(runs.c.id).label("rid")).group_by(runs.c.version_id).subquery()
        )
        current = records.join(latest_versions, records.c.version_id == latest_versions.c.vid)
        current = current.outerjoin(latest_runs, records.c.version_id == latest_runs.c.version_id)
        current = current.outerjoin(
            predictions,
            (predictions.c.record_id == records.c.id) & (predictions.c.run_id == latest_runs.c.rid),
        )
        with self.engine.connect() as conn:
            frame = pd.read_sql(
                select(
                    records.c.customer_id,
                    latest_versions.c.dataset_id,
                    predictions.c.probability,
                    predictions.c.risk_level,
                ).select_from(current),
                conn,
            )
            ever = set(conn.execute(select(versions.c.dataset_id).join(runs).distinct()).scalars())
        frame["status"] = [
            "Đã dự báo" if pd.notna(p) else "Cần dự báo lại" if did in ever else "Chưa dự báo"
            for p, did in zip(frame["probability"], frame["dataset_id"])
        ]
        return frame
