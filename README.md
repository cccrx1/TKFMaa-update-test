# TKFMaa 资源更新隔离测试

本仓库仅用于验证 TKFMaa 的资源更新机制，不是正式下载源。

测试客户端和每个测试资源包的更新地址均须指向本仓库。
游戏资源的开发源码在原项目统一维护，本仓库保存测试自动化、测试说明和测试发布附件。
测试发布不证明游戏任务或异常恢复分支已完成验收。

## 手动运行自动打包

在 Actions 中选择 **Prepare or publish TKFMaa update**，点击 **Run workflow**：

- `source_sha` 填已审核的主仓库完整 40 位提交，不从浮动 main 或历史快照构建。
- `version` 填候选版本；只有批准在线发布时才选择递增的发布版本。
- `kind` 为 `resource` 或 `full-mirror`；后者只镜像主仓库已公开且带来源记录的同版本完整包。
- `publish` 默认关闭，只生成可下载的 Artifact。
- 开启发布前必须完成客户端验收，提供绑定版本、源码和候选清单 SHA256 的 `acceptance_json` 与 `release_notes`。发布工具核验草稿附件后才公开，不覆盖已有公开版本。

该流程只读主仓库源码与完整包，写权限仅用于本测试仓库。资源发布还要求固定仓库变量 `TKFM_CHANNEL_BASELINE_SHA256`，部署模板本身不会配置变量或发布版本。首次部署先执行 `publish: false` 验证。

`resource-test.yml` 已停用发布 job，保留只读历史构建；`resources-candidate.yml` 仍只生成 Artifact。下面的快照与 beta 版本说明用于追溯旧实验，不是新流程的源码入口。

## 资源来源和检查

`source-snapshot/` 保存从主项目工作区导出的运行源码、活动 YAML 与必要的校验工具。`snapshot.json` 记录主项目基准提交、未提交修改路径和逐文件 SHA256；快照包含尚未提交的体力修复和过期活动清理，不能只用基准提交表示全部内容。

`source.json` 的 `source_snapshot` 模式从快照重新构建 Interface、Pipeline、图片与 Agent，不沿用旧包的游戏逻辑。beta.2 资源包仅提供 OCR 模型，模型逐文件大小与 SHA256 必须与主项目 `tools/ocr_model.json` 一致。包内更新源与 Windows Agent 路径在打包时改为测试客户端布局。原 `overrides/` 仅供历史模式使用，本模式不加载旧标记覆盖文件。

构建环境固定 Python 3.12、MaaFramework 5.14.3 和 maa-tools 1.0.23。Schema 从 MaaFramework 固定提交取得。发布前执行路径与校验和检查、打包重现性测试、JSON Schema、maa-tools、资源加载、Agent 导入和 Custom 注册检查。

运行环境、用户配置、日志和缓存不进入资源包。测试包始终指向本仓库。现有版本不覆盖，已发表测试版本不能被较低版本替代；未完成的草稿只能用一致的文件继续上传。

beta.3 验证标记 B → C 的纯打包机制；beta.4 使用真实源码快照，包含体力地图稳定等待与详情确认修复，移除已过期的 Trick or Sweet 六个关卡。构建成功不等于设备验收通过，客户端升级与体力任务结果另行记录。

beta.4 已暴露旧配置的关卡序号迁移问题：MFAAvalonia 2.16.2 保留旧 `index`，删除前置活动后原“关卡-3”实际变成“陷阱-4”。更新后必须重新确认关卡；自动选择迁移尚未通过，不能将本测试流程直接作为无人值守正式发布方案。

beta.5 加入定向重置：根据有序关卡名称生成内部选项标识，列表变化时旧选择失效，显示名称保持“体力消耗关卡”。默认“请重新选择关卡”，未选择时只提示并跳过，不进入游戏导航。实际关卡 Case 才放行原流程；其他设置保留。列表不变的识别参数修复不改变选项标识。升级、提示和重选后运行须通过客户端单独验收。

beta.5 已验证重置与无游戏输入，提示未在界面显示；beta.6 将提示改为当前动作的 `Node.Action.Starting` 回调，继续验证可见提示与重选。

beta.7 按维护者要求撤回上述重选占位方案：移除占位项、提示和入口拦截，旧选择失效后直接默认首个真实关卡，当前为“万圣鹿娘大横行！ - 关卡-1”。更换列表布局摘要，避免删除旧占位项再次导致序号错位。仅列表变更才重置，其他任务和恢复设置保留。

## 本地检查

```powershell
python -m pip install -r tools/requirements.txt
npm ci
python -m unittest discover -s tests -p 'test_*.py' -v
python tools/build_resource.py --version v1.0.7-beta.7
python tools/validate_resource.py
node tools/check_maa.mjs
```

每次构建使用干净的工作目录。`build/`、`dist/`、`.cache/` 和虚拟环境都不提交。
Artifact 中的 `package-manifest.json` 与 `validation.json` 供检查，Release 仅上传 ZIP 和 SHA256 文件。

## 从当前源码直接构建的候选流程

`resources-candidate.yml` 验证主项目新资源构建流程，输入为 `candidate/` 中已在本机审核和验收的公开源码，来源及文件哈希见 `candidate-source.json`。构建与校验步骤和主项目 `.github/workflows/resources.yml` 相同，仅调整测试仓库路径和更新源。

该流程直接按模型锁恢复 OCR，不读取旧 beta 发布包；构建六种桌面目标的资源 ZIP、SHA256 和清单。所有测试产物的更新地址固定指向本测试仓库，权限只有 `contents: read`，只上传 Artifact，不创建标签或 Release。

历史 `resource-test.yml` 与 `source-snapshot/` 保留供既有测试追溯，不由候选流程调用。候选构建通过仍需分别确认正式仓库的提交推送，以及正式资源发布源和版本；本流程不会自动切换正式客户端。
