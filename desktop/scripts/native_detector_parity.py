"""Independent pyFAI geometry reference; the native child cannot run Python."""
import json
import os
os.environ["HDF5_PLUGIN_PRELOAD"]="::"
import tempfile
from pathlib import Path
import numpy as np
import pyFAI
from pyFAI.detectors import Detector
from pyFAI.geometry import Geometry
from native_reference_client import Native, ROOT

PARAMS=dict(dist=.2,poni1=.0003,poni2=.0004,rot1=.01,rot2=-.02,rot3=.03,
            pixel1=95e-6,pixel2=80e-6,wavelength=.4e-10,polarization_factor=.96)

def spline(path):
    def values(numbers):
        return "\n".join("".join(f"{v:14.7E}" for v in numbers[i:i+5]) for i in range(0,len(numbers),5))+"\n\n"
    text="SPATIAL DISTORTION SPLINE INTERPOLATION COEFFICIENTS\n\nVALID REGION\n"+values([0,0,12,8])
    text+="GRID SPACING, X-PIXEL SIZE, Y-PIXEL SIZE\n"+values([2500,80,95])
    for axis in ("X","Y"):
        coefficients=[.13*(i*i/9-j/3) if axis=="X" else .17*(j*j/9-i/3) for i in range(4) for j in range(4)]
        text+=axis+"-DISTORTION\n8 8\n"+values([0]*4+[12]*4+[0]*4+[8]*4+coefficients)
    path.write_text(text)

def main():
    receipts=[]
    with tempfile.TemporaryDirectory() as directory:
        directory=Path(directory)
        for kind in ("spline","nonuniform","curved"):
            d=Detector(pixel1=95e-6,pixel2=80e-6,max_shape=(8,12),orientation=3)
            definition=directory/f"{kind}.nxs"
            if kind=="spline":
                definition=directory/"distortion.spline";spline(definition);d.set_splineFile(str(definition))
            else:
                corners=np.zeros((8,12,4,3),np.float32)
                for r in range(8):
                    for c in range(12):
                        for k,(dr,dc) in enumerate([(0,0),(1,0),(1,1),(0,1)]):
                            y=(r+dr)*95e-6;x=(c+dc)*80e-6+(15e-6 if c>=6 else 0)
                            corners[r,c,k]=[-x*x/.1 if kind=="curved" else 0,y,x]
                d.set_pixel_corners(corners);d.IS_FLAT=kind!="curved";d.mask=np.zeros((8,12),np.int8);d.mask[1,4]=1;d.save(str(definition))
            # Calibrated physical incidence, including distortion and mapped
            # surface normals. pyFAI supplies the orientation-3 reference;
            # detector orientation must permute both centers and normals.
            kwargs={k:v for k,v in PARAMS.items() if k not in ("pixel1","pixel2","polarization_factor")}
            base_absorption=Geometry(detector=d,**kwargs).calc_transmission(np.exp(-40/150), (8,12)).copy()
            for orientation in (1,2,3,4):
                d._orientation=orientation
                kwargs={k:v for k,v in PARAMS.items() if k not in ("pixel1","pixel2","polarization_factor")}
                reference=Geometry(detector=d,**kwargs)
                solid=reference.solidAngleArray((8,12))
                data=120*solid*reference.polarization((8,12),factor=.96)
                source=directory/f"{kind}-{orientation}.npy";np.save(source,np.flipud(data))
                with Native() as n:
                    n.call("open_image",path=str(source))
                    n.call("distortion_file" if kind=="spline" else "detector_file",path=str(definition))
                    n.call("calibration_setup",orientation=orientation)
                    n.call("integration_settings",bins=32,cake_bins=18,trim_zeros=False)
                    result=n.call("manual_geometry",convention="pyfai",values=PARAMS)
                    errors=[]
                    for r,c in [(0,0),(1,5),(4,7),(7,11)]:
                        actual=n.call("pixel",x=c,y=r)["pixel"]["twoTheta"]
                        expected=float(reference.tth(np.array([r],float),np.array([c],float))[0])*180/np.pi
                        errors.append(abs(actual-expected))
                    assert max(errors)<1e-6,(kind,orientation,errors)
                    intensities=np.array(result["pattern"]["y"]);intensities=intensities[intensities!=0]
                    assert intensities.size
                    np.testing.assert_allclose(intensities,120,rtol=3e-6,atol=1e-5,err_msg=f"{kind} orientation {orientation}")
                    corrected=n.call("integration_correction",kind="oiadac",enabled=True)
                    preview=n.call("integration_correction_preview",kind="oiadac")["correctionPreview"]
                    expected_absorption=base_absorption
                    if orientation in (1,2): expected_absorption=expected_absorption[::-1,:]
                    if orientation in (1,4): expected_absorption=expected_absorption[:,::-1]
                    actual_absorption=n.raster(preview,"raster")
                    np.testing.assert_allclose(actual_absorption,expected_absorption,rtol=2e-7,atol=1e-8)
                    np.testing.assert_allclose(n.raster(corrected,"image"),n.raster(result,"image")/expected_absorption,rtol=2e-7)
                    n.call("integration_correction",kind="oiadac",enabled=False)
                    before=n.call("integration_diagnostics")["integrationDiagnostics"]
                    n.call("integrate");diagnostics=n.call("integration_diagnostics")["integrationDiagnostics"]
                    assert diagnostics["patternPlanBuilds"]==before["patternPlanBuilds"]
                    assert diagnostics["cakePlanBuilds"]==before["cakePlanBuilds"]
                    export=directory/f"export-{kind}-{orientation}.poni";n.call("save_calibration",path=str(export))
                    external=pyFAI.load(str(export))
                    # PONI rows are top-down; Dioptas' scientific rows are bottom-up.
                    expected=reference.center_array(shape=(8,12),unit="2th_rad");actual=np.flipud(external.center_array(shape=(8,12),unit="2th_rad"))
                    np.testing.assert_allclose(actual,expected,rtol=0,atol=1e-8)
                    if orientation==3:
                        project=directory/f"{kind}.dio";n.call("save_project",path=str(project))
                        definition.rename(definition.with_suffix(definition.suffix+".moved"))
                        try:
                            restored=n.call("open_project",path=str(project))
                            np.testing.assert_allclose(restored["pattern"]["y"],result["pattern"]["y"],rtol=1e-10,atol=1e-8)
                        finally:definition.with_suffix(definition.suffix+".moved").rename(definition)
                    receipts.append(dict(kind=kind,orientation=orientation,max_angle_error_degrees=max(errors),max_constant_error=float(np.max(abs(intensities-120))),diagnostics=diagnostics))
    out=ROOT/"desktop/artifacts/native-detectors";out.mkdir(parents=True,exist_ok=True)
    (out/"reference.json").write_text(json.dumps(dict(pyfai=pyFAI.version,cases=receipts),indent=2)+"\n")
    print(json.dumps(dict(cases=len(receipts),max_angle_error_degrees=max(r["max_angle_error_degrees"] for r in receipts)),indent=2))
if __name__=="__main__":main()
