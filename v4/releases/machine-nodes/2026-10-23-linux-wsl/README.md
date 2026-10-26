# Linux / Windows WSL2 节点安装入口

这是约0.5MB的轻量安装包。下述真实安装、登录和采集结果来自上一G137版本；G138包目前仅源码和离线包核验，尚未实际安装或跑任务。修复默认 Debian 官方软件源的 Git 安装传输，并对索引错误明确停止；APT软件包安装阶段600秒、索引更新180秒、APT单连接20秒、零重试，原签名校验保留。133文件运行时仅portable_node.py更新；其余132文件保持原版。Node无缓存下载新增父进程整体120秒时限，超时终止并回收本次下载子进程；原INTENT保留，不自动重试，不换资源版本或哈希。该时限不代表整个安装总时限，也不保证网络加速。原Mac插件、OTA和旧任务不受影响。

已有节点解压后直接运行：

```sh
sh install-linux.sh --root /原安装目录 --check
sh bind-linux.sh --root /原安装目录 --status
```

更新前先正常停止节点，再运行 `sh install-linux.sh --root /原安装目录 --upgrade`。原配置、SID、身份和outbox保留，不重新配对；检查/状态读取不采集。正常启动用 `sh start-linux.sh --root /原安装目录`。

新节点由邀请人通过正常配对提供仅该worker的私有配置，并在本机准备有授权的Pro SDK、Signer和CookieBridge。公开包不包含这些私有组件、Cookie或密钥，不静默克隆私仓。安装器检查Git、uv、Python3.12；系统权限/软件源允许时自动安装Git，uv及受管Python使用固定摘要。无安装权限时明确停止交邀请人处理，不索密码。

旁边若有 `bootstrap-cache` 目录，会自动校验并复用其中公开的uv/Python/Node归档，无需另填参数；显式 `--bootstrap-cache` 优先。可选单文件本地缓存kit含这三份官方归档，不含Git系统包、SDK或凭据，不纳入Git发行。没有缓存仍走正常下载，首次安装可能较慢。绑定时优先复用原SID，否则选择本机Bridge唯一的小红书客户端；歧义停止，不猜账号。账号过期或验证码仍需正常登录。

验收范围：独立空工具容器真实安装Git/curl/CA；新节点完整安装已用已有系统Python/Git、全新HOME和节点目录、相同公开缓存完成（29秒、退出0）；同机原浏览器登录复用、单次Pro采集及96云回执/20秒断网恢复已实际通过；全新浏览器登录仍未验。两者不是“完全空OS一次完整安装”的证据。Windows WSL2宿主和物理Linux仍未实机验收；不承诺跨端OTA或任意新机零前置开箱。

## Windows WSL2 入口（尚待真机验收）

Owner先确认原机已有WSL2发行版（当前默认名称Ubuntu，可显式选择已存在发行版），为该新节点正常配对并准备合法本机Pro/Signer/Bridge；不能复制其它设备SID、Cookie、venv或Owner密钥。私有配置、root、依赖和outbox留在WSL Linux HOME，包代码可从Windows解压目录只读运行。

在PowerShell包目录运行：

```powershell
.\windows-wsl.ps1 -Action install
.\windows-wsl.ps1 -Action check
.\windows-wsl.ps1 -Action bind
.\windows-wsl.ps1 -Action bind -LinuxArguments @('--status')
```

缺省root自动取同一WSL用户HOME下的`.local/share/CrowdWorker`，不要求手填路径或ClientID；显式`--root`两种写法不变。正式开始用`-Action start`，该动作可能领取/采集，仅在正常配对、登录、能力许可后操作。脚本没有自动安装WSL、绕开管理员/重启、改变系统ExecutionPolicy或扩大发行版选择；这些以原机实际预检为准。

公开启动代码包含原x64/arm64资源合同；无缓存时按Linux实际uname选择原官方依赖。配套旧arm64缓存不能用于x64，x64缓存与Windows真实安装另验，不因模拟测试通过宣称已支持Windows实机。
