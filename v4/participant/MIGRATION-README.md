# 原标准安装重新接通

已有标准更新助手：解压后双击 `reconnect.command`。新版完整 Mac 安装包的 `install.command` 也会自动识别并走这条路径。

只读取原更新助手自己的固定 config.directory，验证原4.2.8等标准安装的完整权限/入口形状；保留原插件目录、身份、浏览器资料、Cookie、待回传记录、更新偏好及native状态。不会强制重载、关闭浏览器或访问采集来源；随后由原插件在正常空闲更新检查中接入已签名新版。本人私人测试与旧KOL不同权限安装明确拒绝硬迁移，仍保留原通道。

修改helper前在原helper目录生成私有 migration-backup-*，包括helper/config/state与原注册文件。安装器持有原锁，pending/staging或busy拒绝；安装失败恢复原helper/config/注册文件及原执行权限，native state和插件文件不会被安装器改写。系统launchd注册的极端失败仍须按保存备份恢复核验，不能把隔离测试称宿主安装通过。

首次安装：运行完整 Mac 包 `install.command`，按提示加载已解压扩展并通过Owner邀请确认采集。Mac14+/Chrome120+，helper未Apple notarize；系统确认由本人完成。原自动更新关闭偏好不会被强制开启。

成功后也保留备份。原更新助手固定目录中的 `migration-backup-* / backup.json` 记录 slot 对应原文件；slot 0 是原helper、1是原config，随后是native注册与两个LaunchAgent文件，state.json是只读留档。需要人工撤销helper迁移时，先停止采集并确认没有pending/staging，使用选定成功迁移的备份恢复这些helper/注册文件和原执行权限；不得直接覆盖当前state.json，否则会丢新签名序号或回执握手状态。来源插件版本回退通过Owner单独签名恢复通道完成，不卸载身份、不复制浏览器Profile。正常安装失败已自动恢复已改的helper/config/注册文件；原插件和native状态不由安装器写入。
