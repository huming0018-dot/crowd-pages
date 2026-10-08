# v4 私有 Mac 分发

先从 canonical `crawler-extension/v4` 构建，再生成安装包：

```sh
python3 v4/test_release.py /path/to/crawler-extension/v4
python3 v4/build_trial.py --source /private/crowd-extension.zip \
  --invitation-file /private/mac-trial.json --output /private/Mac轻量内测.zip
```

构建器验证源协议、版本、worker与所有文件摘要，注入仍有效的原私有邀请，重新生成交付摘要。说明页版本自动取自客户端 manifest。包内 `release.json` 与旁边 `.sha256` 是产物事实；当前验收状态统一见 crowd-kol/docs/V4_ITERATION.md。

更新助手沿用原 v4 目录。本人必须在原浏览器刷新扩展并核对版本；不能静默授权。保留原个人资料、插件目录与参与身份，不要卸载重报。不要加载到原生产v3个人资料，两条协议共享历史扩展ID但身份不同。

本工具不报名、不扩容邀请、不发布 Pages/CRX、不变更 updates.xml。含私人邀请的安装ZIP禁止提交或上传公开Release。真实参与者采集仍以后台实际回传为准。

## 已有参与者更新

`build_update.py`从不含邀请的canonical源包构建`v4/releases/crowd-v4.1.3-update-mac.zip`。该包只更新原Mac、Chrome/Edge个人资料中已安装的v4；未找到原安装或找到多个身份时停止，不创建新身份。原浏览器存储不删除，用户不需要Codex或开发环境。

```sh
python3 v4/test_update.py /private/crowd-extension.zip
python3 v4/build_update.py --source /private/crowd-extension.zip --output v4/releases/crowd-v4.1.3-update-mac.zip
```

无邀请更新包可以提供给已有参与者，不能用它开放新报名。下载后运行更新助手，在自动打开的原扩展管理页确认刷新，再回到原插件继续；不能承诺解压扩展后台静默升级。管理员通过既有自愿诊断确认版本，再核对真实proof与证据字段，不要求参与者复制正文或接入Codex。

4.1.3是空白导航失败时停止与诊断补充的候选包，尚未在故障设备验收。此更新包仍不提供自动升级；相关渠道审计与设计见 crowd-kol/docs/UPDATE_DIAGNOSTICS.md。

## 4.2.0一次接通自动更新

`build_bootstrap.py`组合canonical扩展与已编译通用Native Messaging助手，生成`releases/crowd-v4.2.0-bootstrap-mac.zip`。它只接续原v4目录，要求macOS 14+并保留开发者模式；用户接通并刷新一次，以后插件每小时校验签名清单、原子替换并只重载自己。可在插件关闭自动更新。无邀请、无新报名、无浏览器策略修改；增加的本机恢复任务只检查未确认更新，不联网或启动采集。

构建：`python3 v4/build_bootstrap.py --source CANONICAL_ZIP --helper UNIVERSAL_HOST --output BOOTSTRAP_ZIP`；检查：`python3 v4/test_bootstrap.py CANONICAL_ZIP UNIVERSAL_HOST`。

`channel.json`为签名发布清单，ZIP URL必须固定提交；不得上传签名私钥、混接根目录旧updates.xml或使用含邀请包。运行版本必须由客户端/宿主握手确认。4.2.0机制已在隔离Mac Chrome实测升级和坏代码回退；原设备首次接通与真实采集仍待验收。
