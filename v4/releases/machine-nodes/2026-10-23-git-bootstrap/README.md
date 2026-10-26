# Linux arm64 节点：依赖安装与原账号复用

这是约0.5MB的轻量安装包。修复默认 Debian 官方软件源的 Git 安装传输，并对索引错误明确停止；APT软件包安装阶段600秒、索引更新180秒、APT单连接20秒、零重试，原签名校验保留。包内133文件运行时未换版。原Mac插件、OTA和旧任务不受影响。

已有节点解压后直接运行：

```sh
sh install-linux.sh --root /原安装目录 --check
sh bind-linux.sh --root /原安装目录 --status
```

更新前先正常停止节点，再运行 `sh install-linux.sh --root /原安装目录 --upgrade`。原配置、SID、身份和outbox保留，不重新配对；检查/状态读取不采集。正常启动用 `sh start-linux.sh --root /原安装目录`。

新节点由邀请人通过正常配对提供仅该worker的私有配置，并在本机准备有授权的Pro SDK、Signer和CookieBridge。公开包不包含这些私有组件、Cookie或密钥，不静默克隆私仓。安装器检查Git、uv、Python3.12；系统权限/软件源允许时自动安装Git，uv及受管Python使用固定摘要。无安装权限时明确停止交邀请人处理，不索密码。

旁边若有 `bootstrap-cache` 目录，会自动校验并复用其中公开的uv/Python/Node归档，无需另填参数；显式 `--bootstrap-cache` 优先。可选单文件本地缓存kit含这三份官方归档，不含Git系统包、SDK或凭据，不纳入Git发行。没有缓存仍走正常下载，首次安装可能较慢。绑定时优先复用原SID，否则选择本机Bridge唯一的小红书客户端；歧义停止，不猜账号。账号过期或验证码仍需正常登录。

验收范围：独立空工具容器真实安装Git/curl/CA；新节点完整安装已用已有系统Python/Git、全新HOME和节点目录、相同公开缓存完成（29秒、退出0）；登录与云回执仍在验收中。两者不是“完全空OS一次完整安装”的证据。Windows WSL2宿主和物理Linux仍未实机验收；不承诺跨端OTA或任意新机零前置开箱。
