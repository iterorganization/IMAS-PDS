#!/usr/bin/env python3
"""Export a MATLAB .mat file (MCLS library configuration) to YAML with types and shapes recoverable.

One-off tool, used once to write ``controllers/CCS/mcls/mcls_library_defaults.yaml`` from
``Config_MCLS.mat`` of pcssp-iter@8b30ca4b (``device_lib/MCLS/MCLS_publicConfiguration/Config_MCLS.mat``,
provenance in ``controllers/CCS/mcls/third_party/PROVENANCE.md``). Kept to redo the export after a library
update and to check the YAML against the .mat.

Usage (module ``IMAS-MUSCLE3/1.0.0-intel-2025b-pds`` gives numpy, scipy and pyyaml)::

    python mat_to_yaml_mcls.py <Config_MCLS.mat> <out.yaml> [--source TEXT]   # export, then round-trip check
    python mat_to_yaml_mcls.py --check <Config_MCLS.mat> <file.yaml>           # check only

Encoding (read back in MATLAB by ``controllers/CCS/mcls/mcls_load_table.m``, which converts the YAML to JSON
with pyyaml + ``json.dumps`` and decodes it with ``jsondecode``):

* a MATLAB double 1x1 with a finite value      -> a plain YAML number;
* a MATLAB char row 1xN (N >= 1)               -> a plain YAML string;
* every other value                            -> a mapping with the key ``matlab_class``:

  - ``{matlab_class: double, size: [r, c], data: [...]}``: values in column-major order; NaN, Inf and -Inf
    are written as the strings ``"NaN"``, ``"Inf"``, ``"-Inf"`` (JSON has no such numbers);
  - ``{matlab_class: char, size: [r, c], data: "..."}``: characters in column-major order;
  - ``{matlab_class: cell, size: [r, c], data: [...]}``: elements in column-major order;
  - ``{matlab_class: struct, size: [r, c], fields: [...], data: [{field: value, ...}, ...]}``: elements in
    column-major order, fields in the order of the .mat.

Only the classes found in Config_MCLS.mat are supported (double, char, cell, struct); anything else stops the
export. The .mat is read with ``scipy.io.loadmat(mat_dtype=True)`` so that numeric arrays come back with the
class MATLAB loads (MAT files may store doubles as smaller integer types).
"""

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import scipy.io as sio
import yaml

FORMAT = "pds-mcls-matlab-yaml-1"
NONFINITE = {"NaN": math.nan, "Inf": math.inf, "-Inf": -math.inf}


def load_mat(path):
    """Variables of a .mat file as numpy objects with MATLAB shapes (2-D) and classes."""
    d = sio.loadmat(
        path,
        mat_dtype=True,
        chars_as_strings=False,
        squeeze_me=False,
        struct_as_record=True,
    )
    return {k: v for k, v in d.items() if not k.startswith("__")}


def _num(x):
    """A finite float as an int when integral (readability), else the float itself."""
    x = float(x)
    if x.is_integer() and abs(x) < 2**53:
        return int(x)
    return x


def _num_or_token(x):
    x = float(x)
    if math.isnan(x):
        return "NaN"
    if math.isinf(x):
        return "Inf" if x > 0 else "-Inf"
    return _num(x)


def encode(v):
    """numpy value from loadmat -> YAML-ready python object (see the module docstring)."""
    if not isinstance(v, np.ndarray):
        raise TypeError(f"unexpected python type {type(v)}")
    shape = [int(n) for n in v.shape]
    if len(shape) != 2:
        raise ValueError(f"only 2-D MATLAB values are supported, got shape {shape}")
    if v.dtype.names:  # struct array
        data = []
        for el in v.flatten(order="F"):
            data.append({fn: encode(el[fn]) for fn in v.dtype.names})
        return {
            "matlab_class": "struct",
            "size": shape,
            "fields": list(v.dtype.names),
            "data": data,
        }
    if v.dtype == object:  # cell array
        return {
            "matlab_class": "cell",
            "size": shape,
            "data": [encode(e) for e in v.flatten(order="F")],
        }
    if (
        v.dtype.kind == "U"
    ):  # char array (chars_as_strings=False: one character per element)
        text = "".join(v.flatten(order="F"))
        if shape[0] == 1 and shape[1] >= 1:
            return text
        return {"matlab_class": "char", "size": shape, "data": text}
    if v.dtype == np.float64:
        flat = v.flatten(order="F")
        if v.size == 1 and np.isfinite(flat[0]):
            return _num(flat[0])
        return {
            "matlab_class": "double",
            "size": shape,
            "data": [_num_or_token(x) for x in flat],
        }
    raise TypeError(
        f"unsupported MATLAB class (numpy dtype {v.dtype}); extend the encoder first"
    )


def decode(y):
    """YAML python object -> numpy value shaped as loadmat returns it (for the round-trip check)."""
    if isinstance(y, bool):
        raise TypeError("booleans are not part of this encoding")
    if isinstance(y, int | float):
        return np.array([[float(y)]])
    if isinstance(y, str):
        return np.array([list(y)], dtype="<U1")
    if not isinstance(y, dict) or "matlab_class" not in y:
        raise TypeError(f"not an encoded MATLAB value: {y!r:.80}")
    cls, shape = y["matlab_class"], tuple(y["size"])
    if cls == "double":
        vals = [NONFINITE[x] if isinstance(x, str) else float(x) for x in y["data"]]
        return np.array(vals, dtype=np.float64).reshape(shape, order="F")
    if cls == "char":
        return np.array(list(y["data"]), dtype="<U1").reshape(shape, order="F")
    if cls == "cell":
        out = np.empty(len(y["data"]), dtype=object)
        for i, e in enumerate(y["data"]):
            out[i] = decode(e)
        return out.reshape(shape, order="F")
    if cls == "struct":
        dt = [(f, object) for f in y["fields"]]
        out = np.empty(len(y["data"]), dtype=dt)
        for i, el in enumerate(y["data"]):
            if list(el.keys()) != y["fields"]:
                raise ValueError(
                    f"struct element {i}: fields {list(el.keys())} differ from {y['fields']}"
                )
            for f in y["fields"]:
                out[i][f] = decode(el[f])
        return out.reshape(shape, order="F")
    raise ValueError(f"unknown matlab_class {cls}")


def first_difference(a, b, path="value"):
    """None if a and b (loadmat-like numpy values) are equal in class, shape, field order and value (NaN == NaN)."""
    if a.shape != b.shape:
        return f"{path}: shape {a.shape} vs {b.shape}"
    if bool(a.dtype.names) != bool(b.dtype.names):
        return f"{path}: struct vs non-struct"
    if a.dtype.names:
        if tuple(a.dtype.names) != tuple(b.dtype.names):
            return f"{path}: fields {a.dtype.names} vs {b.dtype.names}"
        for i, (ea, eb) in enumerate(
            zip(a.flatten(order="F"), b.flatten(order="F"), strict=False)
        ):
            for f in a.dtype.names:
                d = first_difference(ea[f], eb[f], f"{path}({i + 1}).{f}")
                if d:
                    return d
        return None
    if (a.dtype == object) != (b.dtype == object):
        return f"{path}: cell vs non-cell"
    if a.dtype == object:
        for i, (ea, eb) in enumerate(
            zip(a.flatten(order="F"), b.flatten(order="F"), strict=False)
        ):
            d = first_difference(ea, eb, f"{path}{{{i + 1}}}")
            if d:
                return d
        return None
    if a.dtype.kind != b.dtype.kind or a.dtype != b.dtype:
        return f"{path}: class {a.dtype} vs {b.dtype}"
    if a.dtype.kind == "U":
        return (
            None
            if np.array_equal(a, b)
            else f"{path}: text {''.join(a.ravel())!r} vs {''.join(b.ravel())!r}"
        )
    return (
        None
        if np.array_equal(a, b, equal_nan=True)
        else f"{path}: values {a.ravel()[:8]} vs {b.ravel()[:8]}"
    )


def check(mat_path, yaml_path):
    with Path(yaml_path).open() as fh:
        doc = yaml.safe_load(fh)
    if doc.get("format") != FORMAT:
        sys.exit(f"{yaml_path}: format {doc.get('format')!r}, expected {FORMAT!r}")
    mat = load_mat(mat_path)
    ylv = doc["variables"]
    if list(ylv.keys()) != list(mat.keys()):
        sys.exit(f"variables differ: yaml {list(ylv.keys())} vs mat {list(mat.keys())}")
    nleaf = 0
    for name, val in mat.items():
        d = first_difference(val, decode(ylv[name]), name)
        if d:
            sys.exit(f"ROUND-TRIP FAIL {d}")
        nleaf += count_leaves(val)
    print(
        f"ROUND-TRIP OK {yaml_path} == {mat_path} ({len(mat)} variable(s), {nleaf} leaf values)"
    )


def count_leaves(v):
    if v.dtype.names:
        return sum(count_leaves(el[f]) for el in v.flatten() for f in v.dtype.names)
    if v.dtype == object:
        return sum(count_leaves(e) for e in v.flatten())
    return 1


def export(mat_path, yaml_path, source):
    mat = load_mat(mat_path)
    doc = {
        "format": FORMAT,
        "source": source,
        "variables": {k: encode(v) for k, v in mat.items()},
    }
    header = (
        "# MCLS library defaults for PDS, exported from a MATLAB .mat file by controllers/CCS/mcls/tools/mat_to_yaml_mcls.py\n"
        "# (do not edit by hand; re-export instead). Encoding: see the docstring of that tool. Read in MATLAB by\n"
        "# controllers/CCS/mcls/mcls_load_table.m. Provenance: controllers/CCS/mcls/third_party/PROVENANCE.md.\n"
    )
    with Path(yaml_path).open("w") as fh:
        fh.write(header)
        yaml.safe_dump(
            doc,
            fh,
            sort_keys=False,
            default_flow_style=None,
            allow_unicode=False,
            width=120,
        )
    print(f"wrote {yaml_path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--check",
        action="store_true",
        help="only compare an existing YAML with the .mat",
    )
    ap.add_argument(
        "--source", default="", help="provenance text stored under 'source'"
    )
    ap.add_argument("mat")
    ap.add_argument("yaml")
    a = ap.parse_args()
    if not a.check:
        export(a.mat, a.yaml, a.source)
    check(a.mat, a.yaml)


if __name__ == "__main__":
    main()
