"""Compare every archived stage with standalone native outputs (diagnostic only)."""
import json
from pathlib import Path
import sys
import numpy as np
reference, actual, report = map(Path, sys.argv[1:])
assert not report.exists(), "Preserve earlier reports"
a = np.load(actual)
archives = {name: np.load(reference / filename) for name, filename in {
    "masks":"frame-validity.npz", "dac":"dac-validity.npz",
    "positions":"positions.npz", "indexed":"indexed-positions.npz",
    "profiles":"raw-observations-and-bank.npz", "reduced":"reduced-observations.npz",
}.items()}
g = json.loads((reference / "geometry.json").read_text())
result = []
for name in a.files:
    if name == "illumination_excluded": x=archives["masks"]["excluded"]
    elif name == "dac_excluded": x=archives["dac"]["excluded"]
    elif name == "detection_scales": x=archives["masks"][name]
    elif name == "omega_bounds": x=archives["positions"][name]
    elif name.startswith("positions_"):
        x=archives["positions"][name.removeprefix("positions_")]
    elif name.startswith("indexed_"):
        x=archives["indexed"][name.removeprefix("indexed_")]
    elif name in ["geometry_vectors", "reciprocal_basis"]: x=np.array(g[name])
    elif name in archives["profiles"].files: x=archives["profiles"][name]
    elif name in archives["reduced"].files: x=archives["reduced"][name]
    else: raise AssertionError(f"Missing independent reference for {name}")
    y=a[name]
    assert x.shape == y.shape, (name,x.shape,y.shape)
    entry={"name":name,"shape":list(x.shape),"bitwiseExact":x.dtype==y.dtype and x.tobytes()==y.tobytes(),"valuesExact":bool(np.array_equal(x,y,equal_nan=True))}
    if x.dtype.kind in "biu":
        entry["passed"]=bool(np.array_equal(x,y))
    else:
        finite=np.isfinite(x)
        entry["finiteMaskExact"]=bool(np.array_equal(finite,np.isfinite(y)))
        difference=x[finite]-y[finite]
        entry["maxAbsoluteDifference"]=float(abs(difference).max(initial=0))
        scale=np.linalg.norm(x[finite])
        entry["relativeL2"]=float(np.linalg.norm(difference)/scale) if scale else 0.0
        # Preserve the original native numerical endpoint gates. Intermediate
        # floating arrays additionally retain measured max/L2 differences.
        entry["passed"]=entry["finiteMaskExact"] and (entry["relativeL2"]<1e-4 if scale else entry["maxAbsoluteDifference"]<1e-10)
        if name in ["geometry_vectors","reciprocal_basis"]:
            entry["passed"] &= entry["maxAbsoluteDifference"] < 1e-10
        if name in ["indexed_predicted","table_predicted","obs_centres"]:
            entry["passed"] &= entry["maxAbsoluteDifference"] < 1e-4
    result.append(entry)
report.write_text(json.dumps({"scope":"Original-count masks through profile integration, corrections and scaling. Integer/boolean structures exact; float differences and declared gates retained.","arrays":result,"allPassed":all(x["passed"] for x in result)},indent=2)+"\n")
print(json.dumps({"arrays":len(result),"exactValues":sum(x["valuesExact"] for x in result),"failed":[x for x in result if not x["passed"]]},indent=2))
assert all(x["passed"] for x in result), "Stage comparison failed; retained complete report"
