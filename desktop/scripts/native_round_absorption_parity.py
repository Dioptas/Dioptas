"""Independent volume/ray integration for the Rust cylinder and sphere models.

The original Python classes remain a legacy comparison, not a runtime. Their
tilted-cylinder, shell and finite-sphere conventions have known geometric errors.
"""
import json
import tempfile
import time
from pathlib import Path

import numpy as np
from numpy.polynomial.legendre import leggauss
from pyFAI.geometry import Geometry
from dioptas.model.util.ImgCorrection import CylinderAbsorptionCorrection, SphereAbsorptionCorrection
from native_reference_client import Native, ROOT


def quadrature(kind, radius, beam, axis, order=80):
    z, wz = leggauss(order)
    a = min(beam / (2 * radius), 1)
    if beam == 0:
        pos = np.c_[radius * z, np.zeros_like(z), np.zeros_like(z)]
        weights = wz
    elif kind == "sphere":
        # Volume element: rho*d(rho)*d(phi)*dx, x runs between sphere faces.
        alpha = (z + 1) * np.arcsin(a) / 2
        phi = np.arange(2 * order) * np.pi / order
        h, rho = radius * np.cos(alpha), radius * np.sin(alpha)
        xx = (h[:, None, None] * z[None, :, None]) + np.zeros((1, 1, len(phi)))
        yy = rho[:, None, None] * np.cos(phi)[None, None, :] + np.zeros((1, order, 1))
        zz = rho[:, None, None] * np.sin(phi)[None, None, :] + np.zeros((1, order, 1))
        pos = np.c_[xx.ravel(), yy.ravel(), zz.ravel()]
        weights = ((wz * np.sin(alpha) * np.cos(alpha)**2)[:, None, None]
                   * wz[None, :, None] * np.ones((1, 1, len(phi)))).ravel()
    else:
        alpha = z * np.arcsin(a)
        h, y = radius * np.cos(alpha), radius * np.sin(alpha)
        xx, yy = h[:, None] * z, np.broadcast_to(y[:, None], (order, order))
        pos = np.c_[xx.ravel(), yy.ravel(), np.zeros(order**2)]
        weights = ((wz * np.cos(alpha)**2)[:, None] * wz).ravel()
    if kind == "cylinder":
        axis = np.asarray(axis)
        incident = np.array([1., 0, 0])
        u = incident - axis * axis[0]
        u /= np.linalg.norm(u)
        v = np.cross(axis, u)
        pos = pos[:, :1] * u + pos[:, 1:2] * v
    return pos, weights / weights.sum()


def transmission(kind, params, tth, azi, order=80):
    radius, mu, beam = (params[k] for k in ["radius", "absorption_coefficient", "beam_width"])
    tilt, rot = np.deg2rad([params.get("axis_tilt", 0), params.get("axis_rotation", 0)])
    axis = np.array([np.sin(tilt)*np.cos(rot), np.sin(tilt)*np.sin(rot), np.cos(tilt)])
    pos, weights = quadrature(kind, radius, beam, axis, order)
    p2 = np.sum(pos**2, axis=1)
    incident = np.array([-1., 0, 0])

    def exit_path(direction, r):
        projected = direction if kind == "sphere" else direction - axis * np.dot(axis, direction)
        a = np.dot(projected, projected)
        b = pos @ projected
        return (-b + np.sqrt(b*b + a * (r*r - p2))) / a

    lin = exit_path(incident, radius)
    wall = params.get("wall_thickness", 0)
    muc = params.get("container_absorption_coefficient", 0)
    incoming_wall = exit_path(incident, radius + wall) - lin if wall and muc else 0
    out = []
    for t, a in zip(np.ravel(tth), np.ravel(azi)):
        direction = np.array([np.cos(t), np.cos(a)*np.sin(t), np.sin(a)*np.sin(t)])
        lout = exit_path(direction, radius)
        outgoing_wall = exit_path(direction, radius + wall) - lout if wall and muc else 0
        out.append(np.sum(weights * np.exp(-mu * (lin + lout) - muc * (incoming_wall + outgoing_wall))))
    return np.array(out)


def main():
    receipts = []
    with tempfile.TemporaryDirectory() as directory, Native() as n:
        directory = Path(directory)
        shape = (24, 32)
        data = np.full(shape, 100.)
        image = directory / "raw.npy"
        np.save(image, data[::-1])
        geometry = dict(dist=0.03, poni1=0.0012, poni2=0.0016,
                        rot1=0.04, rot2=-0.03, rot3=0.01,
                        pixel1=0.0001, pixel2=0.0001, wavelength=5e-11)
        n.call("open_image", path=str(image))
        n.call("manual_geometry", convention="pyfai", values={**geometry, "polarization_factor":0.965})
        n.call("integration_settings", bins=48, cake_bins=12, poisson_errors=True)
        g = Geometry(**geometry)
        pixels = [(0,0), (3,8), (11,20), (23,31), (17,5), (8,30)]
        row, col = np.array(pixels).T
        tth, azi = g.tth(row, col), g.chi(row, col)
        for kind in ["sphere", "cylinder"]:
            for width in [0., 0.12, 0.5]:
                params = dict(radius=0.2, absorption_coefficient=2.3, beam_width=width)
                if kind == "cylinder":
                    params.update(axis_tilt=38., axis_rotation=27., wall_thickness=0.03,
                                  container_absorption_coefficient=1.7)
                start = time.perf_counter()
                r = n.call("integration_correction", kind=kind, enabled=True, parameters=params,
                           **(dict(container=dict(enabled=True)) if kind == "cylinder" else {}))
                cold = time.perf_counter()-start
                expected = transmission(kind, params, tth, azi)
                actual = np.array([100. / n.call("pixel", x=int(c), y=int(r))["pixel"]["value"] for r,c in pixels])
                np.testing.assert_allclose(actual, expected, rtol=8e-5, atol=1e-9)
                # A new frame reuses the geometry/material map, but propagates its
                # original counts independently into intensity and counting std.
                before = n.call("integration_diagnostics")["integrationDiagnostics"]
                np.save(image, (data*2)[::-1])
                start = time.perf_counter()
                doubled = n.call("open_image", path=str(image))
                warm = time.perf_counter()-start
                np.testing.assert_allclose(doubled["pattern"]["y"], np.array(r["pattern"]["y"])*2, rtol=1e-12)
                np.testing.assert_allclose(doubled["pattern"]["sigma"], np.array(r["pattern"]["sigma"])*np.sqrt(2), rtol=1e-12)
                after = n.call("integration_diagnostics")["integrationDiagnostics"]
                assert after["sampleCorrectionBuilds"] == before["sampleCorrectionBuilds"]
                assert after["sampleCorrectionHits"] > before["sampleCorrectionHits"]
                n.call("integration_correction", kind=kind, enabled=False)
                np.save(image, data[::-1]); n.call("open_image", path=str(image))
                receipts.append(dict(kind=kind, beam_width=width, max_relative_error=float(np.max(abs(actual/expected-1))), cold_seconds=cold, warm_seconds=warm))
        # Independent bin weights and original-count variance through both maps.
        rr, cc = np.indices(shape)
        tt, aa = g.tth(rr,cc), g.chi(rr,cc)
        gain = np.ones(shape)
        for kind in ["cylinder", "sphere"]:
            params = dict(radius=.2,absorption_coefficient=1.3,beam_width=0.)
            if kind=="cylinder": params.update(axis_tilt=30.,axis_rotation=20.,wall_thickness=.02,container_absorption_coefficient=1.7)
            n.call("integration_correction",kind=kind,enabled=True,parameters=params,**(dict(container=dict(enabled=True)) if kind=="cylinder" else {}))
            gain /= transmission(kind,params,tt,aa).reshape(shape)
        r=n.call("integration_settings",bins=40,supersampling=3,solid_angle=False,polarization=0.,azimuth_range=[20,65],trim_zeros=False)
        axis=np.asarray(r["pattern"]["x"]);step=axis[1]-axis[0];edge=axis[0]-step/2
        weights=np.zeros((len(axis),data.size))
        for dy in (1/6,1/2,5/6):
            for dx in (1/6,1/2,5/6):
                radial=np.degrees(g.tth(rr+dy-.5,cc+dx-.5)).ravel()
                angular=np.degrees(g.chi(rr+dy-.5,cc+dx-.5)).ravel()
                selected=(angular>=20)&(angular<65)
                indices=np.clip(np.floor((radial-edge)/step).astype(int),0,len(axis)-1)
                np.add.at(weights,(indices[selected],np.flatnonzero(selected)),1/9)
        norm=weights@(.5*(1+np.cos(tt)**2)).ravel()
        signal=weights@(100*gain).ravel()
        variance=(weights**2)@(100*gain**2).ravel()
        expected=np.divide(signal,norm,out=np.zeros_like(signal),where=norm>0)
        std=np.divide(np.sqrt(variance),norm,out=np.zeros_like(signal),where=norm>0)
        # Local tolerance covers the explicitly bounded native angular interpolation.
        np.testing.assert_allclose(r["pattern"]["y"],expected,rtol=8e-5,atol=1e-7)
        np.testing.assert_allclose(r["pattern"]["sigma"],std,rtol=8e-5,atol=1e-8)
        receipts.append(dict(case="independent supersampling weights and counting variance",max_relative_std_error=float(np.max(abs(np.asarray(r["pattern"]["sigma"])[std>0]/std[std>0]-1)))))
        # Sample and capillary formulas use independent attenuation lookups;
        # a nonabsorbing sample still needs its absorbing wall corrected.
        import xraydb
        from dioptas.model.util.calc import wavelength_to_energy
        n.call("integration_correction",kind="sphere",enabled=False)
        params=dict(radius=.2,beam_width=.12,absorption_coefficient=0.,axis_tilt=38.,axis_rotation=27.,wall_thickness=.03)
        r=n.call("integration_correction",kind="cylinder",enabled=True,parameters=params,container=dict(enabled=True,material=dict(mode="formula",formula="SiO2",density=2.23)))
        mu=xraydb.material_mu("SiO2",wavelength_to_energy(geometry["wavelength"]),density=2.23)/10
        actual_mu=r["state"]["integration"]["corrections"]["cylinder"]["parameters"]["container_absorption_coefficient"]
        np.testing.assert_allclose(actual_mu,mu,rtol=5e-12)
        params["container_absorption_coefficient"]=mu
        expected=transmission("cylinder",params,tth,azi)
        actual=np.array([100./n.call("pixel",x=int(c),y=int(r))["pixel"]["value"] for r,c in pixels])
        np.testing.assert_allclose(actual,expected,rtol=8e-5)
        receipts.append(dict(case="formula capillary with nonabsorbing sample",mu_per_mm=float(actual_mu)))
        # Rust -> original Python reader/writer -> Rust. Compare parameters
        # and recalculated native science, not the legacy flawed ray model.
        from dioptas.desktop.session import DesktopSession
        import h5py
        n.call("integration_correction",kind="cylinder",enabled=False)
        for kind in ["cylinder", "sphere"]:
            params=dict(radius=.2,absorption_coefficient=2.3,beam_width=0.)
            if kind=="cylinder": params.update(axis_tilt=38.,axis_rotation=27.,wall_thickness=.03,container_absorption_coefficient=1.7)
            before=n.call("integration_correction",kind=kind,enabled=True,parameters=params,material=dict(mode="manual"),**(dict(container=dict(enabled=True,material=dict(mode="manual"))) if kind=="cylinder" else {}))
            project=directory/f"native-{kind}.dio"
            n.call("save_project",path=str(project))
            with h5py.File(project) as f:
                doc=json.loads(f["state"][()])["configurations"][0]
                assert doc["native_desktop"]["sample_absorption"]["model"]=="uniform-footprint-rays-v1"
            assert "correctionNotice" not in n.call("open_project",path=str(project))
            ref=DesktopSession()
            r=ref.invoke("open_project",dict(path=str(project)))
            assert r["ok"],r
            correction=ref.configuration.img_model._img_corrections.get_correction(kind)
            for k,v in params.items():
                np.testing.assert_equal(correction.get_params()[k],v)
            legacy_project=directory/f"python-{kind}.dio"
            r=ref.invoke("save_project",dict(path=str(legacy_project)))
            assert r["ok"],r
            after=n.call("open_project",path=str(legacy_project))
            assert "corrected geometry" in after["correctionNotice"]
            np.testing.assert_allclose(after["pattern"]["y"],before["pattern"]["y"],rtol=2e-12,atol=1e-10)
            if kind=="cylinder":
                assert after["state"]["integration"]["corrections"][kind]["container"]["enabled"]
            n.call("integration_correction",kind=kind,enabled=False)
            receipts.append(dict(case=f"{kind} Rust/Python project parameter interoperability",legacyRecalculationNotice=True))
        # Larger angles and optical depth test the finite-footprint average
        # away from the small-angle detector case above.
        wide={**geometry,"dist":.003,"rot1":.7,"rot2":.3}
        n.call("manual_geometry",convention="pyfai",values={**wide,"polarization_factor":.965})
        wg=Geometry(**wide)
        wt,wa=wg.tth(row,col),wg.chi(row,col)
        for kind in ["sphere","cylinder"]:
            params=dict(radius=.2,absorption_coefficient=10.,beam_width=.5)
            if kind=="cylinder": params.update(axis_tilt=20.,axis_rotation=70.,wall_thickness=.03,container_absorption_coefficient=1.7)
            n.call("integration_correction",kind=kind,enabled=True,parameters=params,**(dict(container=dict(enabled=True)) if kind=="cylinder" else {}))
            expected=transmission(kind,params,wt,wa)
            actual=np.array([100./n.call("pixel",x=int(c),y=int(r))["pixel"]["value"] for r,c in pixels])
            np.testing.assert_allclose(actual,expected,rtol=8e-5,atol=1e-9)
            n.call("integration_correction",kind=kind,enabled=False)
            receipts.append(dict(case=f"{kind} wide-angle full illumination",muRadius=2.,max_relative_error=float(np.max(abs(actual/expected-1)))))
        # Compare the original sphere in its valid pencil-beam case. Its endpoint
        # clipping/Riemann grid is a less accurate approximation to this integral.
        legacy = SphereAbsorptionCorrection(tth_array=np.rad2deg(tth), azi_array=np.rad2deg(azi), radius=.2, absorption_coefficient=2.3, n_points=10000)
        legacy.update()
        exact = transmission("sphere",dict(radius=.2,absorption_coefficient=2.3,beam_width=0.), tth,azi)
        np.testing.assert_allclose(legacy.get_data(),exact,rtol=8e-5)
        # The old capillary calculation counts four wall crossings in forward
        # pencil transmission. The physical two-crossing limit is exact.
        old = CylinderAbsorptionCorrection(tth_array=np.array([0.,.1]),azi_array=np.array([0.,0.]),radius=.2,absorption_coefficient=2.3,wall_thickness=.03,container_absorption_coefficient=1.7)
        old.update()
        assert abs(float(old.get_data()[0])-np.exp(-2*2.3*.2-4*1.7*.03)) < 1e-6
        receipts.append(dict(legacy_container_forward=float(old.get_data()[0]), physical_container_forward=float(np.exp(-2*2.3*.2-2*1.7*.03))))
    output = ROOT / "desktop/artifacts/native-integration/round-absorption-parity.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipts,indent=2)+"\n")
    print(json.dumps(receipts,indent=2))


if __name__ == "__main__":
    main()
