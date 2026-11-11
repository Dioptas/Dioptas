"""Explicit independent h5py count oracle; never part of the application runtime."""
import argparse
import hashlib
import json
import subprocess
import h5py
import hdf5plugin  # noqa: F401 -- registers the independent Bitshuffle/LZ4 decoder

parser = argparse.ArgumentParser()
parser.add_argument("probe")
parser.add_argument("image")
parser.add_argument("dataset")
parser.add_argument("output")
args = parser.parse_args()
result = json.loads(subprocess.check_output([args.probe, args.image], text=True))
with h5py.File(args.image, "r") as source:
    data = source[args.dataset]
    assert list(data.shape) == [result["frames"], *result["shape"]]
    dtype = {"U16": "<u2", "U32": "<u4"}[result["dtype"]]
    for frame in result["samples"]:
        words = data[frame["frame"]].astype(dtype, copy=False).tobytes()
        actual = hashlib.sha256(words).hexdigest()
        assert actual == frame["sha256"], (frame, actual)
result["oracle"] = {"reader": "h5py", "version": h5py.__version__, "dataset": args.dataset,
                    "comparison": "SHA-256 of original stored scalar words in little-endian order"}
with open(args.output, "w") as output:
    json.dump(result, output, indent=2)
    output.write("\n")
print(f"Independent stored-word counts match for {len(result['samples'])} acquired frames.")
