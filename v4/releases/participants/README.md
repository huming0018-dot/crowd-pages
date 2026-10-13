# 参与者 Mac 安装（4.2.54）

下载 `crowd-v4.2.54-mac.zip`，解压后双击 `install.command`。系统若要求确认，请本人确认。按提示在 Chrome 扩展页加载刚打开目录，再打开 Owner 邀请链接，勾选同意并开始。任务自动领取，成功回传由后台回执确认。可选运行诊断向 Owner 报错，关闭后清除云端状态与历史。

首次安装只需一次；后续已签名更新保留身份和待回传证据，遇登录/验证码由本人处理。此安装需要 macOS 14+、Chrome 120+。现有旧安装不会被覆盖；不要卸载旧身份或另建浏览器资料。当前试验包覆盖小红书参与者采集，七平台机器工作台属于另一入口。

`crowd-v4.2.55-recovery-extension.zip` 为 Owner 的受控恢复包，普通参与者不要直接安装。文件未含账号凭据或 Owner 密钥。核验：`shasum -a 256 -c SHA256SUMS.txt`。新参与者通道为 `../channel-participants.json`；恢复 envelope 不在活动通道。

Mac 人工下载包位于本目录；OTA 为兼容已审 helper 固定 URL 校验，使用上级目录同字节 `crowd-v4.2.54-participant-extension.zip`。恢复同字节别名为上级 `crowd-v4.2.55-participant-recovery-extension.zip`。签名 envelope 指向提交 SHA 固定的不可变 URL。
