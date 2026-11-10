"""Verify the unified archive without executing its contents."""
import hashlib
import json
import sys
import zipfile
from pathlib import PurePosixPath

REQUIRED = {
    "START_HERE.md", "README.md", "RELEASE_INDEX.html", "docs/release_notes.md",
    "docs/scope_and_validation.md", "src/api/server.py", "media/EnergyLine_demo.mp4",
    "electrical/s3_interface/S3_interface.kicad_pro", "electrical/s3_interface/S3_interface.kicad_sch",
    "electrical/s3_interface/S3_interface.kicad_pcb", "electrical/s3_interface/ASSEMBLY.md",
    "electrical/s3_interface/assembly_bom.csv", "electrical/s3_interface/models/Fuse_372_clearance_envelope.wrl",
    "electrical/s3_interface/drc_rev_a.json", "electrical/s3_interface/erc.json",
    "electrical/s3_interface/simulation/results.json", "electrical/s3_interface/simulation/waveforms.csv",
    "wokwi/sketch.ino", "wokwi/diagram.json", "wokwi/PROJECT_URL.txt", "wokwi/README.md",
    "n8n/workflows/run_experiment.json", "n8n/workflows/commission_s3.json",
}


def verify(path):
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None, "ZIP data corrupted"
        names = z.namelist()
        assert len(names) == len(set(names)), "Duplicate archive entry"
        for name in names:
            p = PurePosixPath(name)
            assert not p.is_absolute() and ".." not in p.parts and p.parts[0] == "energyline", name
            assert not set(p.parts) & {"runtime", ".history", "__pycache__", ".git", "node_modules"}, name
            assert not name.endswith((".lck", ".kicad_prl", ".zip", ".db", ".sqlite3")), name
        manifest = json.loads(z.read("energyline/RELEASE_MANIFEST.json"))
        files = manifest["files"]
        assert REQUIRED <= files.keys(), sorted(REQUIRED - files.keys())
        assert set(names) == {"energyline/" + n for n in files} | {"energyline/RELEASE_MANIFEST.json"}
        for name, checksum in files.items():
            assert hashlib.sha256(z.read("energyline/" + name)).hexdigest() == checksum, name
        for layer in ["F_Cu.gtl", "B_Cu.gbl", "F_Mask.gts", "B_Mask.gbs", "F_Silkscreen.gto", "Edge_Cuts.gm1", "PTH.drl", "NPTH.drl"]:
            assert "electrical/s3_interface/fabrication/rev_A/S3_interface-" + layer in files, layer
        drc = json.loads(z.read("energyline/electrical/s3_interface/drc_rev_a.json"))
        assert all(not drc[k] for k in ["violations", "unconnected_items", "schematic_parity"])
        assert json.loads(z.read("energyline/electrical/s3_interface/simulation/results.json"))["passed"]
        assert manifest["hardware_validated"] is False
        print(f"Verified release {manifest['release']}: {len(files)} files, required deliverables, safe paths, exclusions and every file checksum.")
        return manifest


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python3 scripts/verify_release.py path/to/release.zip")
    verify(sys.argv[1])
