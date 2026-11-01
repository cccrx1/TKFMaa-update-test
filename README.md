# TKFMaa 资源更新隔离测试

本仓库仅用于验证 TKFMaa 的资源更新机制，不是正式下载源。

测试客户端和每个测试资源包的更新地址均须指向本仓库。
游戏资源的开发源码在原项目统一维护，本仓库保存测试自动化、测试说明和测试发布附件。
测试发布不证明游戏任务或异常恢复分支已完成验收。

## 手动运行自动打包

在 Actions 中选择 **Build and publish test resources**，点击 **Run workflow**：

- `version` 填递增的测试版本，例如 `v1.0.7-beta.6`。
- `publish` 默认关闭，只生成可下载的 Artifact。
- 勾选 `publish` 后，全部校验通过才会在本仓库发布预发布版。

该流程不在 push、PR 或打标签时自动发布。它不访问正式项目仓库，也不发布正式安装包。

## 资源来源和检查

`source-snapshot/` 保存从主项目工作区导出的运行源码、活动 YAML 与必要的校验工具。`snapshot.json` 记录主项目基准提交、未提交修改路径和逐文件 SHA256；快照包含尚未提交的体力修复和过期活动清理，不能只用基准提交表示全部内容。

`source.json` 的 `source_snapshot` 模式从快照重新构建 Interface、Pipeline、图片与 Agent，不沿用旧包的游戏逻辑。beta.2 资源包仅提供 OCR 模型，模型逐文件大小与 SHA256 必须与主项目 `tools/ocr_model.json` 一致。包内更新源与 Windows Agent 路径在打包时改为测试客户端布局。原 `overrides/` 仅供历史模式使用，本模式不加载旧标记覆盖文件。

构建环境固定 Python 3.12、MaaFramework 5.14.3 和 maa-tools 1.0.23。Schema 从 MaaFramework 固定提交取得。发布前执行路径与校验和检查、打包重现性测试、JSON Schema、maa-tools、资源加载、Agent 导入和 Custom 注册检查。

运行环境、用户配置、日志和缓存不进入资源包。测试包始终指向本仓库。现有版本不覆盖，已发表测试版本不能被较低版本替代；未完成的草稿只能用一致的文件继续上传。

beta.3 验证标记 B → C 的纯打包机制；beta.4 使用真实源码快照，包含体力地图稳定等待与详情确认修复，移除已过期的 Trick or Sweet 六个关卡。构建成功不等于设备验收通过，客户端升级与体力任务结果另行记录。

beta.4 已暴露旧配置的关卡序号迁移问题：MFAAvalonia 2.16.2 保留旧 `index`，删除前置活动后原“关卡-3”实际变成“陷阱-4”。更新后必须重新确认关卡；自动选择迁移尚未通过，不能将本测试流程直接作为无人值守正式发布方案。

beta.5 加入定向重置：根据有序关卡名称生成内部选项标识，列表变化时旧选择失效，显示名称保持“体力消耗关卡”。默认“请重新选择关卡”，未选择时只提示并跳过，不进入游戏导航。实际关卡 Case 才放行原流程；其他设置保留。列表不变的识别参数修复不改变选项标识。升级、提示和重选后运行须通过客户端单独验收。

beta.5 已验证重置与无游戏输入，提示未在界面显示；beta.6 将提示改为当前动作的 `Node.Action.Starting` 回调，继续验证可见提示与重选。

## 本地检查

```powershell
python -m pip install -r tools/requirements.txt
npm ci
python -m unittest discover -s tests -p 'test_*.py' -v
python tools/build_resource.py --version v1.0.7-beta.6
python tools/validate_resource.py
node tools/check_maa.mjs
```

每次构建使用干净的工作目录。`build/`、`dist/`、`.cache/` 和虚拟环境都不提交。
Artifact 中的 `package-manifest.json` 与 `validation.json` 供检查，Release 仅上传 ZIP 和 SHA256 文件。
