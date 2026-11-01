"""Publish validated artifacts only to the isolated test repository."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from build_resource import TEST_REPO, version_key


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    args = parser.parse_args()
    version_key(args.version)
    if os.environ.get("GITHUB_REPOSITORY") != TEST_REPO:
        raise ValueError("Publishing is restricted to the isolated test repository.")
    commit = os.environ.get("GITHUB_SHA", "")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("A concrete workflow source commit is required.")
    manifest = json.loads((args.dist / "package-manifest.json").read_text(encoding="utf-8"))
    validation = json.loads((args.dist / "validation.json").read_text(encoding="utf-8"))
    if not validation.get("passed") or manifest["repository"] != TEST_REPO or manifest["version"] != args.version:
        raise ValueError("Validated package does not match the requested test release.")
    if manifest["source_commit"] != commit:
        raise ValueError("Package comes from a different source commit.")
    expected_name = f"TKFMaa-resource-win-x64-{args.version}.zip"
    if manifest["archive"] != expected_name:
        raise ValueError("Unexpected archive name.")
    archive = args.dist / expected_name
    if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest["sha256"]:
        raise ValueError("Package archive hash mismatch.")
    checksum = args.dist / (archive.name + ".sha256")
    if checksum.read_text(encoding="utf-8") != f"{manifest['sha256']}  {archive.name}\n":
        raise ValueError("Checksum file mismatch.")
    with zipfile.ZipFile(archive) as package:
        if set(package.namelist()) != set(manifest["files"]):
            raise ValueError("Archive file list differs from its manifest.")
        for name, digest in manifest["files"].items():
            if hashlib.sha256(package.read(name)).hexdigest() != digest:
                raise ValueError(f"Archive content differs: {name}")
        interface = json.loads(package.read("interface.json"))
        if interface["github"] != f"https://github.com/{TEST_REPO}" or interface["version"] != args.version:
            raise ValueError("Archive Interface update source or version mismatch.")
    token = os.environ["GITHUB_TOKEN"]
    api = f"https://api.github.com/repos/{TEST_REPO}"

    def request(method, url, payload=None, data=None, content_type="application/json"):
        destination = urllib.parse.urlparse(url)
        if destination.scheme != "https" or destination.hostname not in {"api.github.com", "uploads.github.com"}:
            raise ValueError("Unexpected API host.")
        if not destination.path.startswith(f"/repos/{TEST_REPO}/"):
            raise ValueError("Refusing an API request outside the test repository.")
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, method=method, data=data, headers={
            "Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
            "Content-Type": content_type, "User-Agent": "TKFMaa-resource-test-workflow",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        with urllib.request.urlopen(req, timeout=120) as response:
            return json.load(response)

    releases = request("GET", api + "/releases?per_page=100")
    matching = [item for item in releases if item["tag_name"] == args.version]
    if matching and not matching[0]["draft"]:
        raise ValueError("This test version is already published; published files are never replaced.")
    for release in releases:
        if release["draft"]:
            continue
        try:
            existing = version_key(release["tag_name"])
        except ValueError:
            continue
        if existing >= version_key(args.version):
            raise ValueError("The requested version is not newer than published test versions.")
    notes = f"""## Actions 自动打包隔离测试

资源版本：{args.version}。基线：{manifest['baseline_version']}。
来源提交：{commit}。

已执行 Schema、maa-tools、资源加载、Agent 导入及 Custom 注册检查。
本包使用已记录校验值的主项目工作区源码快照，包含体力地图点击修复与过期活动关卡清理。
活动关卡列表变化后旧选择失效，默认“请重新选择关卡”；未选择时提示并跳过体力任务，其他设置保留。仅识别参数更新而列表不变时不重置。
主项目来源：{manifest.get('source_snapshot', {}).get('base_commit', 'legacy baseline')}；快照可能包含未提交修改，以 Artifact 清单内逐文件校验值为准。
本工作流未连接设备，游戏实测结果须另行记录。
资源包仅用于现有 Windows x64 测试客户端，要求 MaaFramework {manifest['required_maafw']} 与既有 Python 环境。
更新地址固定为本测试仓库，不用于正式客户端。

SHA256：`{manifest['sha256']}`
"""
    release = matching[0] if matching else request("POST", api + "/releases", payload={
        "tag_name": args.version, "target_commitish": commit, "name": args.version + " 自动资源打包测试",
        "body": notes, "draft": True, "prerelease": True,
    })
    if release["target_commitish"] != commit:
        raise ValueError("Existing draft targets a different source commit.")
    for path, kind in ((archive, "application/zip"), (checksum, "text/plain")):
        digest = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        assets = [item for item in release["assets"] if item["name"] == path.name]
        if assets:
            if assets[0].get("digest") != digest:
                raise ValueError("Existing draft attachment differs; refusing to replace it.")
            continue
        url = release["upload_url"].split("{", 1)[0] + "?name=" + urllib.parse.quote(path.name)
        asset = request("POST", url, data=path.read_bytes(), content_type=kind)
        if asset.get("digest") != digest or asset["size"] != path.stat().st_size:
            raise ValueError("Uploaded attachment integrity check failed.")
    release = request("GET", api + f"/releases/{release['id']}")
    if {item["name"] for item in release["assets"]} != {archive.name, checksum.name}:
        raise ValueError("Unexpected release attachments.")
    published = request("PATCH", api + f"/releases/{release['id']}", payload={"draft": False, "prerelease": True, "make_latest": "false"})
    print(published["html_url"])


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as error:
        raise SystemExit(f"GitHub API returned HTTP {error.code}.") from None
