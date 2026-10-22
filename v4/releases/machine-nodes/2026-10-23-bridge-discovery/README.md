# Linux / Windows WSL2 节点入口：CookieBridge 原始布局发现修复

本包只修复安装器的原 CookieBridge 自动发现：按上游真实 `server/app.py` 识别，避免要求不存在的 `pyproject.toml`。Pro SDK 与 Signer 原发现/校验不变；缺失或多个候选仍明确停止，不猜路径。

源码提交 `019b5bd38bad8a1a6903d7c2b5585071bab28346`。相对 G138 已发布包仅安装器及包清单变化，其余145文件相同。147文件的轻包不含Pro SDK、Signer、CookieBridge、账号、Cookie、worker配置或公共依赖归档；133运行文件保持G138的 `63073aea928a3107a463c6150677738afb9de48628ecb6dcc1b600fb2024a20a`，不是整份当前Git HEAD。

## 安装前提

邀请人须通过正常配对提供该节点独立的 worker-only 私有配置，并在本机准备合法Pro/Signer/CookieBridge。不能复制其他节点身份、SID、Cookie、venv或Owner密钥。包可放Windows解压目录（WSL `/mnt/c/...`）；节点root、依赖、身份和outbox应在WSL Linux HOME。

安装器使用Python3.12；若系统只有3.14，原入口将安装私有受管3.12.14，不替换系统Python或改shell配置。Git/curl/CA缺失时仍需正常系统安装权限。邻接 `bootstrap-cache` 可复用经原SHA核验的官方uv/Python/Node归档，按实际arm64/x86_64选择；缓存不是私有SDK或身份。无缓存仍走原官方下载及Node整体120秒下载界限，不代表整个安装120秒。

## 正常入口

Linux已准备合法本机依赖和该节点配置后：

```sh
sh install-linux.sh
sh install-linux.sh --root /原安装目录 --check
sh bind-linux.sh --root /原安装目录 --status
```

已有节点升级先通过正常流程停止节点，再使用原目录的 `--upgrade`；保留原身份和outbox，不重新配对。已有未确认写入/待回传任务须先正常对账，不能清状态强行升级。

Windows已有Ubuntu WSL2时，在PowerShell包目录使用原入口：

```powershell
.\windows-wsl.ps1 -Action install
.\windows-wsl.ps1 -Action check
.\windows-wsl.ps1 -Action bind -LinuxArguments @('--status')
```

默认root为同一WSL用户HOME的 `.local/share/CrowdWorker`。首次认证、绑定与start须在原身份核验、合法本机浏览器登录及正常授权后另行执行。若原机ExecutionPolicy禁止脚本，停止并由操作者按原系统权限处理；本包不修改策略、不自动安装WSL或重启、不绕过权限。

## 已验与未验

本次已验：源码回归、增量包完整性、147普通文件/清单哈希、原runtime保持；三份官方x64归档的SHA与ELF64/x86_64只读校验。Windows实机仅确认Win11/Ubuntu WSL2/x86_64、系统Python3.14.4和Git2.53；本包尚未Windows实装、登录或执行任务。原Linux arm64 Docker的安装/原登录复用/96ACK和断网恢复是之前版本证据，不能代替本包或Windows验收。

物理Linux、原生Windows、Windows首次浏览器登录、跨端OTA、本轮真实采集和云回执仍未通过本发行验收。原Mac插件、OTA渠道、旧任务和UNKNOWN不变。本目录只是本地发行候选，未发布。
