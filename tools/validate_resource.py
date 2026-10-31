"""Validate the staged package without a device; resource and Agent checks use separate processes."""

import ast
import json
from pathlib import Path
import subprocess
import sys
import urllib.request

from jsonschema import validators
from referencing import Registry, Resource


ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = ["pipeline.schema.json", "interface.schema.json", "interface_import.schema.json",
           "interface_config.schema.json", "custom.action.schema.json", "custom.recognition.schema.json"]


def main():
    config = json.loads((ROOT / "source.json").read_text(encoding="utf-8"))
    stage = ROOT / "build/package"
    schema_dir = ROOT / ".cache/schemas"
    schema_dir.mkdir(parents=True, exist_ok=True)
    base = f"https://raw.githubusercontent.com/MaaXYZ/MaaFramework/{config['schema_commit']}/tools/"
    resources = []
    schemas = {}
    for name in SCHEMAS:
        path = schema_dir / name
        if not path.exists():
            urllib.request.urlretrieve(base + name, path)
        schema = json.loads(path.read_text(encoding="utf-8"))
        schema.setdefault("$id", base + name)
        schemas[name] = schema
        resources.append((base + name, Resource.from_contents(schema)))
    registry = Registry().with_resources(resources)
    def validate(path, name):
        schema = schemas[name]
        cls = validators.validator_for(schema)
        cls.check_schema(schema)
        cls(schema, registry=registry).validate(json.loads(path.read_text(encoding="utf-8-sig")))
    validate(stage / "interface.json", "interface.schema.json")
    pipelines = sorted((stage / "resource/pipeline").rglob("*.json"))
    registered = {"custom_action": set(), "custom_recognition": set()}
    referenced = {key: set() for key in registered}
    for path in (stage / "agent").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in registered:
                if node.args and isinstance(node.args[0], ast.Constant):
                    registered[node.func.attr].add(node.args[0].value)
    def visit(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in referenced and isinstance(child, str):
                    referenced[key].add(child)
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    for path in pipelines:
        validate(path, "pipeline.schema.json")
        visit(json.loads(path.read_text(encoding="utf-8-sig")))
    visit(json.loads((stage / "interface.json").read_text(encoding="utf-8-sig")))
    for kind in registered:
        if referenced[kind] - registered[kind]:
            raise ValueError(f"Unregistered {kind}: {sorted(referenced[kind] - registered[kind])}")
    subprocess.run([sys.executable, "-B", "-c", "from maa.resource import Resource; from maa.tasker import Tasker; import sys; Tasker.set_log_dir(sys.argv[2]); r=Resource(); j=r.post_bundle(sys.argv[1]).wait(); assert j.succeeded and r.loaded; print('Resource load OK')", str(stage / "resource"), str(ROOT / "build/logs")], check=True, cwd=ROOT)
    subprocess.run([sys.executable, "-B", "-c", "import sys; sys.path.insert(0,sys.argv[1]); import main; print('Agent imports OK')", str(stage / "agent")], check=True, cwd=ROOT)
    report = {"passed": True, "pipeline_files": len(pipelines), "schema_revision": config["schema_commit"],
              "resource_load": "passed", "agent_imports": "passed", "custom_references": {key: len(value) for key, value in referenced.items()},
              "device_tests": "not_run", "known_limitations": ["Existing stamina stage-click defect is not fixed by this packaging test."]}
    (ROOT / "dist/validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
