"""Download the group's exact trusted Random Forest handoff, verifying its digest."""

import hashlib
from pathlib import Path
import urllib.request

MODEL_URL = "https://drive.google.com/uc?export=download&id=1PpBMLvQrMJHmnt6ETPfjrnfeKG_ciBm0"
SHA256 = "19d97aeff847a990ea1a3f6c27f95975e41df9275d7e8913084c16c98c865f48"


def main():
    target = Path(__file__).resolve().parents[1] / "models/best_model_v1.pkl"
    if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == SHA256:
        print("Model already present; SHA256 verified.")
        return
    with urllib.request.urlopen(MODEL_URL, timeout=90) as response:
        content = response.read()
    if hashlib.sha256(content).hexdigest() != SHA256:
        raise ValueError(
            "Model checksum mismatch. The download may be a Google Drive login page; no file saved."
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".download")
    temporary.write_bytes(content)
    temporary.replace(target)
    print("Trusted model downloaded; SHA256 verified.")


if __name__ == "__main__":
    main()
