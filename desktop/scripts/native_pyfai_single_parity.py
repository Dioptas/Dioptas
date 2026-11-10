"""Frozen-executable bitwise checks for typed interactive integration admission."""

import argparse
import json
import os
import tempfile
from pathlib import Path

os.environ["HDF5_PLUGIN_PRELOAD"] = "::"
import h5py
import numpy as np
import native_reference_client as client
from native_pyfai_single_benchmark import CachedNative, signature


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--before", type=Path, required=True)
    p.add_argument("--after", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    receipts = []
    with tempfile.TemporaryDirectory(prefix="pyfai-single-parity-") as temp:
        directory = Path(temp)
        shape = (43, 57)
        data = np.random.default_rng(123).integers(
            0, 65536, size=(3, *shape), dtype=np.uint32
        )
        data[0, 0, :4] = [0, 1, 2**31, 2**32 - 1]
        for dtype in ["uint16", "uint32", "float64"]:
            with h5py.File(directory / (dtype + ".h5"), "w") as f:
                f["counts"] = data.astype(dtype)
        for name, values in [
            ("background", np.full(shape, 17.0)),
            ("flat", np.broadcast_to(np.linspace(0.8, 1.2, shape[1]), shape)),
            ("mask", (data[0] % 13 == 0).astype(np.uint8)),
        ]:
            np.save(directory / (name + ".npy"), values)
        geometry = dict(
            dist=0.12,
            poni1=0.0017,
            poni2=0.0021,
            rot1=0.01,
            rot2=-0.03,
            rot3=0.02,
            pixel1=0.0001,
            pixel2=0.00012,
            wavelength=0.5e-10,
            polarization_factor=0.965,
        )
        for dtype in ["uint16", "uint32", "float64"]:
            reference = {}
            for variant, executable in [("before", args.before), ("after", args.after)]:
                client.EXECUTABLE = executable
                with CachedNative({"RAYON_NUM_THREADS": "4"}) as n:

                    def check(label, action, **kw):
                        r = n.call(
                            action,
                            requested_products=dict(cake=True, rings=False),
                            **kw,
                        )
                        sig = signature(n, r)
                        if variant == "before":
                            reference[label] = sig
                        else:
                            assert sig == reference[label], (dtype, label)
                            receipts.append(
                                dict(dtype=dtype, case=label, bitwiseEqual=True)
                            )
                        return r

                    n.call("manual_geometry", convention="pyfai", values=geometry)
                    n.call(
                        "integration_settings",
                        method="pyfai_full",
                        bins=67,
                        cake_bins=19,
                        trim_zeros=False,
                    )
                    check(
                        "open",
                        "open_image",
                        path=str(directory / (dtype + ".h5")),
                        dataset="counts",
                    )
                    for errors in [True, False]:
                        check(
                            f"errors-{errors}",
                            "integration_settings",
                            poisson_errors=errors,
                        )
                        for i in range(2):
                            check(
                                f"next-{errors}-{i}",
                                "next_image",
                                direction=1 if i == 0 else -1,
                            )
                        check(f"resident-{errors}", "integrate")
                    check("mask", "mask_file", path=str(directory / "mask.npy"))
                    check("roi", "integration_roi", limits=[2, 38, 3, 51])
                    check(
                        "q", "integration_settings", unit="q_A^-1", poisson_errors=True
                    )
                    check("d", "integration_settings", unit="d_A", trim_zeros=True)
                    check(
                        "sector",
                        "integration_settings",
                        azimuth_range=[150.0, -150.0],
                        solid_angle=False,
                    )
                    check("bin-change", "integration_settings", bins=83)
                    check("spread", "integration_settings", azimuthal_std=True)
                    check(
                        "restore-fixed",
                        "integration_settings",
                        unit="2th_deg",
                        azimuth_range=None,
                        solid_angle=True,
                        azimuthal_std=False,
                    )
                    check(
                        "dynamic",
                        "mask_plugin",
                        name="Threshold Mask",
                        enabled=True,
                        settings=dict(above_enabled=True, above_value=60000.0),
                    )
                    check("dynamic-next", "next_image", direction=1)
                    check(
                        "dynamic-disabled",
                        "mask_plugin",
                        name="Threshold Mask",
                        enabled=False,
                    )
                    check(
                        "background",
                        "integration_image_background",
                        path=str(directory / "background.npy"),
                        scale=0.7,
                        offset=1.2,
                        poisson=True,
                    )
                    check(
                        "flat",
                        "integration_flat_field",
                        path=str(directory / "flat.npy"),
                    )
                    check("corrected-next", "next_image", direction=1)
                    check(
                        "background-disabled",
                        "integration_image_background",
                        reset=True,
                    )
                    check("flat-disabled", "integration_flat_field", enabled=False)
                    # Exact rotation/flip handling must continue through the
                    # established resident path rather than the raw addresses.
                    check("transform", "image_transform", operation="flip_horizontal")
                    check("transformed-next", "next_image", direction=-1)
                    if variant == "after":
                        diagnostics = n.call("integration_diagnostics")[
                            "integrationDiagnostics"
                        ]
                        assert (diagnostics["typedImageIntegrations"] > 0) == (
                            dtype != "float64"
                        ), diagnostics
            print("PASS", dtype, flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(dict(cases=receipts, bitwiseEqual=True), indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
