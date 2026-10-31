# TKFMaa 资源更新隔离测试

本仓库仅用于验证 TKFMaa 的资源更新机制，不是正式下载源。

测试客户端和每个测试资源包的更新地址均须指向本仓库。
游戏资源的开发源码在原项目统一维护，本仓库保存测试自动化、测试说明和测试发布附件。
测试发布不证明游戏任务或异常恢复分支已完成验收。

## 手动运行自动打包

在 Actions 中选择 **Build and publish test resources**，点击 **Run workflow**：

- `version` 填递增的测试版本，例如 `v1.0.7-beta.3`。
- `publish` 默认关闭，只生成可下载的 Artifact。
- 勾选 `publish` 后，全部校验通过才会在本仓库发布预发布版。

该流程不在 push、PR 或打标签时自动发布。它不访问正式项目仓库，也不发布正式安装包。

## 资源来源和检查

`source.json` 固定本测试仓库已有的 beta.2 资源包及 SHA256。`overrides/` 保存此次资源覆盖文件，`remove` 声明要从新包中移除的旧文件。构建得到包含 Interface、资源与 Agent 的完整 Windows x64 资源包。

构建环境固定 Python 3.12、MaaFramework 5.14.3 和 maa-tools 1.0.23。Schema 从 MaaFramework 固定提交取得。发布前执行路径与校验和检查、打包重现性测试、JSON Schema、maa-tools、资源加载、Agent 导入和 Custom 注册检查。

运行环境、用户配置、日志和缓存不进入资源包。测试包始终指向本仓库。现有版本不覆盖，已发表测试版本不能被较低版本替代；未完成的草稿只能用一致的文件继续上传。

首次测试仅替换 beta.2 的标记 B 为标记 C，以及版本和说明。原有体力关卡点击问题未修复，不应将构建成功解释为全部游戏任务已通过。

## 本地检查

```powershell
python -m pip install -r tools/requirements.txt
npm ci
python -m unittest discover -s tests -p 'test_*.py' -v
python tools/build_resource.py --version v1.0.7-beta.3
python tools/validate_resource.py
node tools/check_maa.mjs
```

每次构建使用干净的工作目录。`build/`、`dist/`、`.cache/` 和虚拟环境都不提交。
Artifact 中的 `package-manifest.json` 与 `validation.json` 供检查，Release 仅上传 ZIP 和 SHA256 文件。
