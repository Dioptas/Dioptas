"""Independent Python XrayDB checks for the native attenuation-only dataset."""
import json
import tempfile
from pathlib import Path

import numpy as np
import xraydb
from dioptas.model.util.calc import wavelength_to_energy, energy_to_wavelength

from native_reference_client import Native, ROOT


def main():
    receipts = []
    with tempfile.TemporaryDirectory() as directory, Native() as n:
        directory = Path(directory)
        source = directory / "counts.npy"
        np.save(source, np.full((24, 32), 100.0))
        n.call("open_image", path=str(source))
        geometry = dict(dist=0.13, poni1=0.0012, poni2=0.0016,
                        rot1=0.008, rot2=-0.013, rot3=0.02,
                        pixel1=0.0001, pixel2=0.0001, wavelength=energy_to_wavelength(20000),
                        polarization_factor=0.965)
        n.call("manual_geometry", convention="pyfai", values=geometry)
        n.call("integration_settings", bins=48, cake_bins=12, poisson_errors=True)
        for kind in ["plate", "slab", "cylinder", "sphere"]:
            n.call("integration_correction", kind=kind, enabled=True,
                   parameters=(dict(thickness=0.00001) if kind in ("plate","slab") else dict(radius=0.00001,beam_width=0.)),
                   material=dict(mode="formula", formula="C", density=3.51))
            for formula, density in [("C", 3.51), ("CeO2", 7.22), ("Fe0.7Mg0.3O", 4.0),
                                     ("Ca3(PO4)2", 3.14), ("Au", 19.32), ("kapton", 0)]:
                n.call("integration_correction", kind=kind, enabled=True,
                       material=dict(mode="formula", formula=formula, density=density))
                for energy in [1000., 5000., 7111.9, 7112.1, 20000., 100000., 800000.]:
                    geometry["wavelength"] = energy_to_wavelength(energy)
                    automatic = n.call("manual_geometry", convention="pyfai", values=geometry)
                    actual = automatic["state"]["integration"]["corrections"][kind]["parameters"]["absorption_coefficient"]
                    expected = xraydb.material_mu(formula, wavelength_to_energy(geometry["wavelength"]),
                                                 **(dict(density=density) if density else {})) / 10
                    np.testing.assert_allclose(actual, expected, rtol=5e-12, atol=1e-12)
                    manual = n.call("integration_correction", kind=kind, enabled=True,
                                    parameters=dict(absorption_coefficient=float(expected)),
                                    material=dict(mode="manual"))
                    for key in ["y", "sigma"]:
                        np.testing.assert_allclose(automatic["pattern"][key], manual["pattern"][key], rtol=5e-12, atol=1e-8)
                    n.call("integration_correction", kind=kind, enabled=True, material=dict(mode="formula"))
                receipts.append(dict(kind=kind, formula=formula, density=density, energies=7))
            before = n.call("state")
            for material in [dict(formula="NotAnElement"), dict(density=-1), dict(mode="other")]:
                assert not n.invoke("integration_correction", kind=kind, enabled=True, material=material)["ok"]
                assert n.call("state") == before
            bad = {**geometry, "wavelength": energy_to_wavelength(50)}
            assert not n.invoke("manual_geometry", convention="pyfai", values=bad)["ok"]
            assert n.call("state") == before
            n.call("integration_correction", kind=kind, enabled=False)
    output = ROOT / "desktop/artifacts/native-integration/material-parity.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipts, indent=2) + "\n")
    print(json.dumps(receipts, indent=2))


if __name__ == "__main__":
    main()
