"""Independent diagnostics only: no Python enters either numerical worker.

Usage: python scxrd_compare_standalone.py STANDALONE_DIR DESKTOP_DIR ABLATION_JSON NEW_REPORT
NumPy reads archived native products; no source HKL or atomic model is loaded.
"""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

standalone, desktop, ablation, output = map(Path, sys.argv[1:])
assert not output.exists(), "Preserve prior comparisons"
a = np.load(standalone / "reduced-observations.npz")
d = json.loads((desktop / "reduction.json").read_text())
rows = d["reflections"]
h = a["hkl"]
use = a["use"]

def rint(intensity, sigma, selected):
    families = {}
    for i in np.flatnonzero(selected):
        # Pbca plus Friedel, in the identical supplied orthorhombic setting.
        families.setdefault(tuple(abs(h[i])), []).append(i)
    numerator = denominator = 0.0
    repeated = 0
    for ids in families.values():
        if len(ids) < 2:
            continue
        repeated += 1
        values, weights = intensity[ids], 1.0 / sigma[ids] ** 2
        mean = np.sum(values * weights) / np.sum(weights)
        numerator += np.sum(abs(values - mean))
        denominator += np.sum(abs(values))
    return {"rInt": numerator / denominator, "observations": int(selected.sum()),
            "families": len(families), "repeatedFamilies": repeated}

checks = {"hklExact": bool(np.array_equal(h, [r["hkl"] for r in rows])),
          "flagsExact": bool(np.array_equal(a["flags"], [r["flags"] for r in rows])),
          "useMaskExact": bool(np.array_equal(use, [r["native_use"] for r in rows]))}
source = json.loads((standalone / "frame-validity.json").read_text())
checks["allPreparedFrameHashesExact"] = source["raw_frame_hashes"] == d["shadows"]["sourceHashes"]
mask = np.load(standalone / "frame-validity.npz")
checks["illuminationMaskBytesExact"] = hashlib.sha256(mask["excluded"].tobytes()).hexdigest() == d["shadows"]["illuminationSha256"]
assert np.array_equal(mask["detection_scales"], d["shadows"]["detectionScales"])
legacy = json.loads(ablation.read_text())
checks["dacMaskMatchesFrozenGeometryAblation"] = legacy["cases"][-1]["shadows"]["dacSha256"] == d["shadows"]["dacSha256"]
errors = {}
for name in ["intensity", "sigma"]:
    x = a[name]
    y = np.array([r[name] if r[name] is not None else np.nan for r in rows])
    checks[f"{name}FiniteMaskExact"] = bool(np.array_equal(np.isfinite(x), np.isfinite(y)))
    finite = np.isfinite(x)
    delta = abs(x - y)
    z = delta[use] / a["sigma"][use]
    errors[name] = {
        "allFiniteRelativeL2": float(np.linalg.norm((x-y)[finite]) / np.linalg.norm(x[finite])),
        "usedRelativeL2": float(np.linalg.norm((x-y)[use]) / np.linalg.norm(x[use])),
        "usedMaxDifferenceInReferenceSigma": float(z.max()),
        "usedP95DifferenceInReferenceSigma": float(np.percentile(z,95)),
    }
    # Frozen PhaseSmith v29/v9 equivalence gates, unchanged for this repair.
    assert errors[name]["allFiniteRelativeL2"] < 1e-4
assert errors["intensity"]["usedMaxDifferenceInReferenceSigma"] < 0.1
assert errors["intensity"]["usedP95DifferenceInReferenceSigma"] < 0.01
assert all(checks.values()), checks
geom = json.loads((standalone / "geometry.json").read_text())
geom_max = float(np.max(abs(np.array(geom["geometry_vectors"]) - np.array([d["geometry"][k] for k in ["origin","fast","slow","beam","axis"]]))))
# Attribution on a fixed finite-aperture subset, never a production eligibility rule.
centres = np.load(standalone / "raw-observations-and-bank.npz")["obs_centres"]
origin, fast, slow, beam, axis = np.array(geom["geometry_vectors"])
ray = origin + centres[:,0,None]*fast + centres[:,1,None]*slow
ray /= np.linalg.norm(ray, axis=1)[:,None]
beam /= np.linalg.norm(beam)
axis /= np.linalg.norm(axis)
e = np.array([0.,1.,0.])
physical = abs(np.cross(ray,beam) @ axis) / (.98*(1-(ray @ e)**2) + .02*(1-(ray @ np.cross(beam,e))**2))
common = use & np.all(np.isfinite(a["aperture"][:,:2]),axis=1) & (a["aperture"][:,1] > 0)
variants = {}
for name, intensity, sigma in [
    ("native-aperture-physical-only", a["aperture"][:,0]*physical, a["aperture"][:,1]*physical),
    ("native-profile-physical-only", a["raw_profiles"][:,0]*physical, a["raw_profiles"][:,1]*physical),
    ("native-profile-family-scaled", a["intensity"], a["sigma"]),
]:
    variants[name] = rint(intensity, sigma, common)
report = {
    "scope": "Measured reduction parity only; no atomic model/reference intensities used. Supplied cell, group, DAC opening and provisional angles are explicit priors.",
    "engine": d["engine"], "adapter": d["adapter"],
    "sourceHashes": source["raw_frame_hashes"], "checks": checks,
    "rows": len(rows), "used": int(use.sum()),
    "retainedMismatchWarnings": int(np.count_nonzero(((a["flags"] & 131072) != 0) & use)),
    "standalone": rint(a["intensity"], a["sigma"], use),
    "desktop": d["scaling"], "errors": errors, "maximumGeometryVectorDifference": geom_max,
    "fixedTrackMaskAblation": [{"case": c["case"], "rInt": c["scaling"]["rInt"], "observations": sum(r["flags"] == 0 for r in c["reflections"])} for c in legacy["cases"]],
    "fixedCommonNativeObservations": variants,
    "selectionNote": "3955 finite-aperture rows are an attribution subset; production uses all 4125 native-eligible rows, including 660 MISMATCH warnings. All earlier failed artifacts retained.",
    "standaloneSearch": json.loads((standalone / "workflow-result.json").read_text()),
}
output.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({k:report[k] for k in ["checks","rows","used","retainedMismatchWarnings","standalone","errors","maximumGeometryVectorDifference","fixedTrackMaskAblation","fixedCommonNativeObservations"]},indent=2))
