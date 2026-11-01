"""Create a full Windows x64 resource package, exclusively for the test repo."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import urllib.request
import zipfile


ROOT = Path(__file__).resolve().parent.parent
TEST_REPO = "cccrx1/TKFMaa-update-test"


def version_key(version):
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)-beta\.(\d+)", version)
    if not match:
        raise ValueError("Use a test version such as v1.0.7-beta.3.")
    return tuple(map(int, match.groups()))


def safe_name(name):
    path = PurePosixPath(name)
    if not name or "\\" in name or path.is_absolute() or ":" in name:
        raise ValueError(f"Unsafe package path: {name}")
    if any(part in {"", ".", ".."} for part in name.split("/")):
        raise ValueError(f"Unsafe package path: {name}")
    if not (name == "interface.json" or name.startswith(("resource/", "agent/"))):
        raise ValueError(f"Unexpected package root: {name}")
    if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo", ".log"}:
        raise ValueError(f"Cache or log in resource package: {name}")
    return path


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def read_baseline(path, expected_sha256):
    if sha256(path.read_bytes()) != expected_sha256:
        raise ValueError("Baseline SHA256 does not match the reviewed release.")
    files = {}
    with zipfile.ZipFile(path) as archive:
        if sum(item.file_size for item in archive.infolist()) > 512 * 1024 * 1024:
            raise ValueError("Baseline expands beyond the resource package limit.")
        names = set()
        for item in archive.infolist():
            if item.is_dir():
                continue
            safe_name(item.filename)
            if item.filename.casefold() in names:
                raise ValueError("Duplicate or case-colliding archive entries.")
            names.add(item.filename.casefold())
            if stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError("Symlinks are not accepted in resource packages.")
            files[item.filename] = archive.read(item)
    return files


def write_archive(path, files):
    with zipfile.ZipFile(path, "x", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            safe_name(name)
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data, compresslevel=9)


def read_snapshot(root):
    metadata = json.loads((root / "snapshot.json").read_text(encoding="utf-8"))
    if metadata["repository"] != "cccrx1/TKFMaa" or not re.fullmatch(r"[0-9a-f]{40}", metadata["base_commit"]):
        raise ValueError("Unexpected source snapshot provenance.")
    expected = metadata["files"]
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p.name != "snapshot.json"}
    if actual != set(expected):
        raise ValueError("Source snapshot inventory differs from its reviewed manifest.")
    files = {}
    extras = {"LICENSE", "assets/stamina/active.yaml", "tools/build_stamina_activities.py",
              "tools/add_interaction_stability.py", "tools/requirements.txt", "tools/ocr_model.json"}
    for name, digest in expected.items():
        if name == "assets/interface.json":
            target = "interface.json"
        elif name.startswith("assets/resource/"):
            target = name.removeprefix("assets/")
        elif name.startswith("agent/"):
            target = name
        elif name in extras:
            target = None
        else:
            raise ValueError(f"Unexpected source input: {name}")
        if ".." in PurePosixPath(name).parts or "\\" in name or ":" in name or PurePosixPath(name).is_absolute():
            raise ValueError("Unsafe source input path.")
        path = root / name
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root.parent):
            raise ValueError("Source symlinks are not accepted.")
        data = path.read_bytes()
        if sha256(data) != digest:
            raise ValueError(f"Source input hash mismatch: {name}")
        if target is not None:
            safe_name(target)
            files[target] = data
    return files, metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--baseline-archive", type=Path)
    args = parser.parse_args()
    config = json.loads((ROOT / "source.json").read_text(encoding="utf-8"))
    if config["repository"] != TEST_REPO or os.getenv("GITHUB_REPOSITORY", TEST_REPO) != TEST_REPO:
        raise ValueError("This builder is restricted to the isolated test repository.")
    if version_key(args.version) <= version_key(config["baseline_version"]):
        raise ValueError("Target version must be newer than the baseline.")
    prefix = f"https://github.com/{TEST_REPO}/releases/download/{config['baseline_version']}/"
    if not config["download_url"].startswith(prefix):
        raise ValueError("Baseline must come from the pinned test release.")
    stage = ROOT / "build/package"
    dist = ROOT / "dist"
    if stage.exists() or dist.exists():
        raise ValueError("Build outputs already exist; use a clean checkout for each build.")
    baseline = args.baseline_archive or ROOT / ".cache/baseline.zip"
    if not baseline.exists():
        baseline.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(config["download_url"], baseline)
    baseline_files = read_baseline(baseline, config["sha256"])
    provenance = None
    if config.get("mode") == "source_snapshot":
        files, provenance = read_snapshot(ROOT / "source-snapshot")
        model = json.loads((ROOT / "source-snapshot/tools/ocr_model.json").read_text(encoding="utf-8"))
        for item in model["files"]:
            name = "resource/model/ocr/" + item["name"]
            safe_name(name)
            data = baseline_files[name]
            if len(data) != item["bytes"] or sha256(data) != item["sha256"]:
                raise ValueError("Baseline OCR model differs from the source model lock.")
            files[name] = data
    else:
        files = baseline_files
        for name in config.get("remove", []):
            safe_name(name)
            if name not in files:
                raise ValueError(f"Expected removed file was absent: {name}")
            del files[name]
        for path in (ROOT / "overrides").rglob("*"):
            if path.is_symlink():
                raise ValueError("Overlay symlinks are not accepted.")
            if path.is_file():
                name = path.relative_to(ROOT / "overrides").as_posix()
                safe_name(name)
                files[name] = path.read_bytes()
    interface = json.loads(files["interface.json"].decode("utf-8-sig"))
    if interface["name"] != "TKFMaa" or (not provenance and interface["version"] != config["baseline_version"]):
        raise ValueError("Unexpected baseline project or version.")
    if provenance:
        if interface["agent"] != {"child_exec": "python", "child_args": ["../agent/main.py"]}:
            raise ValueError("Unexpected source Agent command.")
        interface["agent"] = {"child_exec": "./python/python.exe", "child_args": ["./agent/main.py"]}
    if interface["agent"] != {"child_exec": "./python/python.exe", "child_args": ["./agent/main.py"]}:
        raise ValueError("Unexpected Windows packaged Agent command.")
    interface.update(version=args.version, github=f"https://github.com/{TEST_REPO}", description=config["description"])
    files["interface.json"] = (json.dumps(interface, ensure_ascii=False, indent=4) + "\n").encode("utf-8")
    for name, data in files.items():
        destination = stage.joinpath(*safe_name(name).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    dist.mkdir(parents=True)
    archive = dist / f"TKFMaa-resource-win-x64-{args.version}.zip"
    write_archive(archive, files)
    archive_hash = sha256(archive.read_bytes())
    (dist / (archive.name + ".sha256")).write_text(f"{archive_hash}  {archive.name}\n", encoding="utf-8")
    manifest = {"version": args.version, "repository": TEST_REPO, "baseline_version": config["baseline_version"],
                "baseline_sha256": config["sha256"], "source_commit": os.getenv("GITHUB_SHA", "local"),
                "required_maafw": config["maafw_version"], "platform": "win-x64", "archive": archive.name,
                "sha256": archive_hash, "files": {name: sha256(data) for name, data in sorted(files.items())}}
    if provenance:
        manifest["source_snapshot"] = provenance
    (dist / "package-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"version": args.version, "files": len(files), "bytes": archive.stat().st_size, "sha256": archive_hash}))


if __name__ == "__main__":
    main()
