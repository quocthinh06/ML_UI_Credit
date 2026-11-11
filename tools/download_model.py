"""Verify or download the group's trusted model handoffs."""

import argparse
import hashlib
from pathlib import Path
import urllib.request

MODEL_URL = "https://drive.google.com/uc?export=download&id=1PpBMLvQrMJHmnt6ETPfjrnfeKG_ciBm0"
SHA256 = "19d97aeff847a990ea1a3f6c27f95975e41df9275d7e8913084c16c98c865f48"
MODELS = [
    ("impute_stats_v1.pkl", None,
     "7dab4cbe963f5366036fa5d4fc2af694180baad4ad929b11b61144da12f4e38c"),
    ("best_model_v1.pkl", MODEL_URL, SHA256),
    (
        "model_lr_v1.pkl",
        "https://drive.google.com/uc?export=download&id=1ArO7kNI5dGnrGy772oeLdA9jQFIpFo-4",
        "3468f37886cc1917ff7727e6166d2508c6abf5445b707f820d13ae3730053269",
    ),
    (
        "model_xgb_v1.pkl",
        "https://drive.google.com/uc?export=download&id=18BPTkPFeWLuQeOPD1AfBaaAO76hb7Mq0",
        "8a0e0763ffbf7239227b8a1d21031291e4a5bf9f46cca92f3eaa74c73dc3da5a",
    ),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    for filename, url, digest in MODELS:
        download(filename, url, digest, verify_only=args.verify_only)


def download(filename, url, digest, *, verify_only=False):
    target = Path(__file__).resolve().parents[1] / "models" / filename
    if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == digest:
        print(f"{filename}: SHA256 verified.")
        return
    if verify_only:
        raise ValueError(f"{filename}: missing file or SHA256 mismatch.")
    if url is None:
        raise ValueError(f"{filename}: restore the trusted artifact from the repository.")
    with urllib.request.urlopen(url, timeout=90) as response:
        content = response.read()
    if hashlib.sha256(content).hexdigest() != digest:
        raise ValueError(
            f"{filename}: downloaded file failed SHA256 verification."
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".download")
    temporary.write_bytes(content)
    temporary.replace(target)
    print(f"{filename}: downloaded and SHA256 verified.")


if __name__ == "__main__":
    main()
