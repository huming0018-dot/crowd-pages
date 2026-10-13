# 参与者 Mac 安装（4.2.58）

下载 `crowd-v4.2.58-mac.zip`，解压后双击 `install.command`。系统若要求确认，请本人确认。按提示在 Chrome 扩展页加载刚打开目录，再打开 Owner 邀请链接，勾选同意并开始。任务自动领取，成功回传由后台回执确认。可选运行诊断向 Owner 报错，关闭后清除云端状态与历史。

首次安装只需一次；后续已签名更新保留身份和待回传证据，遇登录/验证码由本人处理。此安装需要 macOS 14+、Chrome 120+。现有旧安装不会被覆盖；不要卸载旧身份或另建浏览器资料。当前试验包覆盖小红书参与者采集，七平台机器工作台属于另一入口。

`crowd-v4.2.59-recovery-extension.zip` 为 Owner 的受控恢复包，普通参与者不要直接安装。文件未含账号凭据或 Owner 密钥。核验：`shasum -a 256 -c SHA256SUMS.txt`。新参与者通道为 `../channel-participants.json`；恢复 envelope 不在活动通道。

Mac 人工下载包位于本目录；OTA 为兼容已审 helper 固定 URL 校验，使用上级目录同字节 `crowd-v4.2.58-participant-extension.zip`。恢复同字节别名为上级 `crowd-v4.2.59-participant-recovery-extension.zip`。签名 envelope 指向提交 SHA 固定的不可变 URL。

56修复自动任务满额换任务、日配额等待、两条验收后等待实验启动并自动继续。57是保留这些修复的独立恢复包，不在活动通道。已有54会从原参与者OTA通道收到56，无需重新安装。已有标准helper安装会自动读取原helper配置并在原目录重新接通，不改Profile、身份、登录与待回传记录；旧KOL权限安装明确拒绝硬迁移。

已有标准更新助手也可单独下载 `crowd-v4.2.58-existing-helper-reconnect.zip`，解压双击 reconnect.command。原helper/config/state和注册文件先备份，保留全部原偏好，busy/pending时拒绝；不强制重载，等原插件正常空闲OTA。58修复任务换取期间的监控误报警，59保留全部56/58状态修复，只回滚回传节奏。新Mac完整包已同时支持首次安装和原标准安装接续。
