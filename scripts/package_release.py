"""Build the unified release, excluding private runtime state and historical drafts."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INCLUDE = {".github", "src", "scripts", "tests", "configs", "docs", "cad", "data", "web", "n8n", "media", "results", "electrical", "wokwi"}
ROOT_FILES = {"render.yaml", "LICENSE", "THIRD_PARTY_NOTICES.md", "CONTRIBUTING.md", "index.html", ".nojekyll", "README.md", "START_HERE.md", "RELEASE_INDEX.html", "release_config.json", "requirements.txt", "requirements-media.txt", ".python-version", ".gitignore", ".dockerignore", "compose.yaml", "Dockerfile"}
OMIT = {"docs/development_history.md", "docs/original_specification.md", "docs/setup_status.md", "results/final/archive_roundtrip_verification.json", "results/final/live_scenario_verification.json", "results/final/unified_release_verification.json", "electrical/build_pcb.py", "electrical/s3_interface/S3_placement_draft.kicad_pcb", "electrical/s3_interface/exports/S3_placement_draft.svg", "electrical/s3_interface/simulation/waveforms.txt"}


def selected_files():
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(ROOT)
        name = rel.as_posix()
        parts = rel.parts
        if parts[0] not in INCLUDE and name not in ROOT_FILES:
            continue
        if name in OMIT:
            continue
        if any(p in {"__pycache__", ".history", ".git", "node_modules", ".venv"} for p in parts):
            continue
        if parts[:2] in {("n8n", "data"), ("results", "experiments"), ("results", "integration"), ("electrical", "runtime"), ("electrical", "release")}:
            continue
        if path.name.startswith(("~", ".env")) or path.name == ".DS_Store":
            continue
        if path.suffix in {".pyc", ".sqlite3", ".db", ".lck", ".kicad_prl", ".zip"}:
            continue
        if path.suffix == ".log" and name != "electrical/s3_interface/simulation/ngspice.log":
            continue
        if parts[0] == "media" and path.suffix == ".png" and path.name not in {"contact_sheet.png", "verified_fault_frame.png"}:
            continue
        yield path, name


def main():
    config = json.loads((ROOT / "release_config.json").read_text())
    folder = ROOT / "release"
    folder.mkdir(exist_ok=True)
    selected = list(selected_files())
    manifest = {
        "release": config["version"], "archive": config["archive"], "scope": config["scope"],
        "files": {name: hashlib.sha256(path.read_bytes()).hexdigest() for path, name in selected},
        "exclusions": ["Credentials and Docker/n8n runtime state", "Live experiment databases and local instance records", "Caches, editor locks, recovery history and scratch work", "Superseded PCB placement draft and nested release archives", "Duplicate raw SPICE text samples; CSV and engine log retained"],
        "start_here": "START_HERE.md", "offline_index": "RELEASE_INDEX.html",
        "reproduce": "python3 scripts/reproduce.py",
        "wokwi_test": "python3 wokwi/test_controller.py (requires a C++ compiler)",
        "electrical_reproduce": "electrical/README.md (KiCad 10.0.3, Docker and ngspice 46)",
        "limitations_file": "docs/scope_and_validation.md",
        "wokwi_url": config["wokwi_url"], "hardware_validated": False,
    }
    encoded = json.dumps(manifest, indent=2) + "\n"
    archive = folder / config["archive"]
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for name, data in [(name, path.read_bytes()) for path, name in selected] + [("RELEASE_MANIFEST.json", encoded.encode())]:
            info = zipfile.ZipInfo("energyline/" + name, date_time=(2026, 11, 10, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            bundle.writestr(info, data)
    (folder / "RELEASE_MANIFEST.json").write_text(encoded)
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (folder / "SHA256SUMS.txt").write_text(f"{checksum}  {archive.name}\n")
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        assert len(bundle.namelist()) == len(manifest["files"]) + 1
        for name, digest in manifest["files"].items():
            assert hashlib.sha256(bundle.read("energyline/" + name)).hexdigest() == digest, name
    print(f"Packaged {len(selected)} files; {archive.stat().st_size:,} bytes. All file checksums verified.")


if __name__ == "__main__":
    main()
