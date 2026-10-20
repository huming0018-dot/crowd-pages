# Pro 官方依赖准备（安装器）

原可见“开始安装.command”沿既有预检和原身份接续。包只含本仓适配器，不分发 Pro SDK、venv、profile 或凭据。

本机已通过厂商授权渠道提供两项目源码后，由安装运营方在原助手目录配置 0600 `pro-dependency-settings.json`；该文件不是扩展消息，也不来自远端任务。固定字段见 `prepare-pro-dependencies.py`：schema/uv/uv_sha256/projects(pro,signer)，每项目 root/commit/files(LICENSE、README.md、pyproject.toml、uv.lock的SHA)/python/python_sha256。解释器固定3.11与3.12，canonical路径和SHA必须一致；不自动下载Python或私SDK。

原安装入口发现该文件即执行官方 `uv sync --frozen` 在线准备，分别写入当前助手私有 `pro-environments/<inputsha>/pro` 与 `signer`。不会移动/复制旧venv、改锁文件、启动Signer、登录或发平台请求。默认在线使用已审官方lock的registry/artifacts；`--offline`仅开发诊断选项，无缓存会如实失败。完成先核本地Pro early-exit协议与准备环境的Signer库import；正常wrapper再使用原 `pro-signer.json` 实际选定的Python/source调用已锁原生 `pro_signer_server.py` 的 `validate_only`（不加 `--serve`），通过后才进入原configure事务。Signer按每次Pro run启动并最终停止，闲置无listener是正常状态，不要求常驻pong。缺SDK/依赖/Signer/账号绑定分别保持未就绪；不冒平台已认证。

`plan`仅本地git/filehash/base interpreter版本检查，不写env，不sync；`prepare`会安装依赖并写独立once证据；`check`不会安装或启动服务；正常wrapper传入上述selected-descriptor只读验证callback。standalone `check` 没有原绑定验证callback时明确not_ready（`signer_binding_required`），不会猜端口。API的显式健康诊断仅由已校验原binding的caller传入，沿原loopback URL请求 `/signsrv/pong`，不用于要求安装时常驻服务。写入once INTENT之后失败/中断保留原INTENT、不生成RESULT，同attempt不自动重跑；前置拒绝不补造INTENT。准备成功同输入只读复核，不重复sync。

原六settings原件与已配置账号根不覆写。正常wrapper对新环境Python沿原双锁/once事务接续 `root/pro-executor.json` 与helper `pro-config.json` 两个Pro Python指针，保存settings前像并生成derived-settings，保留原session/账号/profile/participant字段；失败只回滚已知本次写入，未知不重发。未提供该绑定接续上下文的旧调用仍明确 `dependency_binding_migration_required`，不绕过边界。新机未有合法绑定明确 `dependency_binding_required`；不能复制Owner账号/profile作模板。没有依赖描述文件保持旧安装行为，仍会明确缺已有SDK/Python/绑定。

测试：`/usr/bin/python3 -B -m unittest test_pro_dependencies test_pro_dependency_process test_pro_dependency_installer`；打包整合另需显式 `CROWD_PARTICIPANT_EXTENSION`（已审own EXT ZIP）和 `CROWD_PARTICIPANT_HELPER`（已审universal/helper）后运行 `test_pro_dependency_package`，缺输入fail而非skip。原 `test_participant_package.py` / `test_participant_existing_chain.py` 保持，嵌套zip/脚本SHA必须完整。普通93通道及原安装绑定不因构建此包改变。

源码依据为已购官方本地项目，Pro-Python d32dd565277116ba4880c28ccd417a7c376cb62d / SignSrv26c53d8f3221d95e0d4961b0593debd179d3cf10，各自README推荐uv sync。许可证为非商业学习使用1.1；未经书面同意不得商用，购买不自动证明向普通参与者再分发私源码的权利。本安装器仅消费本设备已有合法工件；团队/OEM/私有发行授权尚须厂商确认，不自造下载渠道。


## 原身份绑定接续（当前 Mac）

原入口在官方锁定依赖准备后，复用原 configure-pro 双锁/once 事务接续 root/pro-executor.json 和 helper pro-config 的 Pro Python。原六项 settings 保留为前像并生成 derived-settings，不覆盖身份、session、账号或浏览器资料。失败仅回滚已知本次指针；未知不重发。

Signer 仍由原 Pro 每次 run 管理，空闲无需常驻监听。安装只用实际选定 pro-signer.json 的 Python/source 调用已锁 pro_signer_server 的 validate_only，不加 --serve；其描述符和解释器 resolve 路径/字节 SHA 保护至最终门。没有迁移第三个 Signer 指针，也不把另一个 prepared 环境视作实际已选择。

当前受审 runtime 的 Node pin 包含原机路径；新 Mac 缺合法 SDK、Node 或 Signer 描述符须明确 not_ready。本接续不等于新机注册、平台认证或来源采集已验收。

The original mc_root remains the MediaCrawler fallback. Selected Pro SDK source is authoritative only in root/pro-executor.json and must match the pinned official dependency descriptor; continuation never rewrites the fallback field.


## Portable Node 资源（仅新源码合同）

新准备/check复用原依赖入口，固定 Node v22.23.2 官方 macOS arm64/x64 archive SHA；安装到当前用户助手的 `node-runtime/<version>-darwin-<arch>`，不修改旧 `NODE-SHA.json` 或用户 PATH。单一自有码 `portable_node.py` 由包内校验后同字节放入安装器顶层和Pro runtime，INSTALL-SHA覆盖两份；Signer仍按原run启动/停止，不新增daemon。prepare会取得公开Node资源，check只校验；未知INTENT不自动续装。Node LICENSE/第三方声明保留，私ProSDK/账号仍只本地合法引用。

产品回归：`/usr/bin/python3 -B test_portable_node.py`（18项），MP默认相邻crowd-kol或显式 `CROWD_MULTIPLATFORM_DIR`，缺仓/源码硬失败不skip；原G29三脚本32项继续运行。操作司机16项保留隔离审计证据，不加入正式回归。arm64官方二进制已离线核等原trustedSHA且原ExecJS成功；PGP未验证、x64未实跑，不冒通用新Mac完成。正式源码接入不更新已安装113文件runtime；当前assembler完整own源码119加新module为120，保原128边界，后续独立组包/签名/本机采用与中央能力登记另验，不把Node源码合入当运行时就绪。
