# Linux arm64 机器节点安装包

[下载安装包（约0.5MB）](https://raw.githubusercontent.com/huming0018-dot/crowd-pages/codex/v4.0.6-handoff/v4/releases/machine-nodes/2026-10-23/crowd-linux-arm64-worker-bootstrap.tar.gz)

这是 Linux arm64 机器节点包；已在 Docker arm64 完成真实采集、云回执和断网恢复。Windows WSL2、物理Linux和全新机完整登录尚未验收。原 Mac 插件、身份、进度、评分和 OTA 通道保持，不用为此重新安装原插件。

## 已有节点

解压后，在包目录运行：

```sh
sh install-linux.sh --root /原安装目录 --check
sh bind-linux.sh --root /原安装目录 --status
```

入口会读取原配置，不要求填写SDK目录、ClientID、Python/uv路径或包摘要。检查和账号状态读取不会启动采集、重新登录或报名。Owner要更新运行版本时，先正常停止原节点，再用同一入口的 `--upgrade`；身份和历史回执保留。开始采集用 `sh start-linux.sh --root /原安装目录`，终端自动领取已有获准任务。

## 新节点由邀请人先准备

邀请人通过正常配对提供该节点的私有配置，并准备已授权的本地Pro、Signer、CookieBridge。不要发Owner密钥，不要复制其他节点身份。标准目录下运行 `sh install-linux.sh`；工具会检查并在条件具备时安装uv和受管Python3.12，也支持校验过的离线缓存。Git只有在已有安装权限及可用系统软件源时才自动安装，本轮apt联网安装未通过；下载/权限失败交邀请人处理，不让参与者手工拼SDK参数。

绑定入口自动复用原SID；无旧绑定时从原本地Bridge选择唯一已连接的小红书客户端，有歧义会停止，不猜账号。真正过期的网页登录或验证码仍需账号本人完成。私有Pro源码、Cookie、密码及云密钥不包含在公开包中。

原安装记录、outbox、身份及已安装旧运行版本均保留。当前精确采集验收为小红书单篇正文和评论/回复，媒体未在本轮请求；不能据此宣称所有平台和跨端OTA已完成。
