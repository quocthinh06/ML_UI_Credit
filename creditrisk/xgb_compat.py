"""Read the supplied XGBoost snapshot through its portable Model JSON.

The supplied snapshot contains zero-count untyped UBJSON arrays. The Windows
snapshot loader rejects these, and py-ubjson 0.16.1 consumes the next byte when
decoding them. Fix that lookahead in an isolated decoder namespace, never in
the installed library or global XGBoost classes. No tree or weight is changed.
"""

import hashlib
import json
import types

import joblib

SOURCE_SHA256 = "8a0e0763ffbf7239227b8a1d21031291e4a5bf9f46cca92f3eaa74c73dc3da5a"


class BoosterState:
    pass


class HandoffUnpickler(joblib.numpy_pickle.NumpyUnpickler):
    def find_class(self, module, name):
        if module == "xgboost.core" and name == "Booster":
            return BoosterState
        return super().find_class(module, name)


def load_portable_handoff(path):
    import ubjson.decoder as decoder
    import xgboost

    if hashlib.sha256(path.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("Chỉ áp dụng bộ đọc tương thích cho đúng SHA256 XGBoost bàn giao.")
    with path.open("rb") as stream:
        bundle = HandoffUnpickler(str(path), stream, ensure_native_byte_order=True).load()
    namespace = dict(vars(decoder))
    for name, function in vars(decoder).items():
        if isinstance(function, types.FunctionType) and function.__module__ == decoder.__name__:
            namespace[name] = types.FunctionType(
                function.__code__, namespace, function.__name__, function.__defaults__, function.__closure__
            )
    original = namespace["__get_container_params"]

    def container_params(read, in_mapping, no_bytes):
        result = original(read, in_mapping, no_bytes)
        _, counting, count, type_ = result
        if (
            counting
            and count == 0
            and (in_mapping or type_ == namespace["TYPE_NONE"])
            and type_ not in namespace["__TYPES_NO_DATA"]
        ):
            read.__self__.seek(-1, 1)
        return result

    namespace["__get_container_params"] = container_params
    estimator = bundle["pipeline"].steps[-1][1]
    snapshot = namespace["loadb"](estimator._Booster.handle, no_bytes=True)
    booster = xgboost.Booster()
    booster.load_model(bytearray(json.dumps(snapshot["Model"]).encode()))
    booster.set_param({"nthread": 1})
    estimator._Booster = booster
    return bundle
