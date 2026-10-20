# Pro 官方依赖准备（安装器）

原可见“开始安装.command”沿既有预检和原身份接续。包只含本仓适配器，不分发 Pro SDK、venv、profile 或凭据。

本机已通过厂商授权渠道提供两项目源码后，由安装运营方在原助手目录配置 0600 `pro-dependency-settings.json`；该文件不是扩展消息，也不来自远端任务。固定字段见 `prepare-pro-dependencies.py`：schema/uv/uv_sha256/projects(pro,signer)，每项目 root/commit/files(LICENSE、README.md、pyproject.toml、uv.lock的SHA)/python/python_sha256。解释器固定3.11与3.12，canonical路径和SHA必须一致；不自动下载Python或私SDK。

原安装入口发现该文件即执行官方 `uv sync --frozen` 在线准备，分别写入当前助手私有 `pro-environments/<inputsha>/pro` 与 `signer`。不会移动/复制旧venv、改锁文件、启动Signer、登录或发平台请求。默认在线使用已审官方lock的registry/artifacts；`--offline`仅开发诊断选项，无缓存会如实失败。完成先核本地Pro early-exit协议与Signer库import，再检查已运行Signer固定本机pong，最后调用原configure。缺SDK/依赖/Signer/账号绑定分别保持未就绪；不冒平台已认证。

`plan`仅本地git/filehash/base interpreter版本检查，不写env，不sync；`prepare`会安装依赖并写独立once证据；`check`不会安装或启动服务，显式本机健康请求只发 `/signsrv/pong`。任何失败/中断留INTENT而不生成RESULT，同attempt不自动重跑。准备成功同输入只读复核，不重复sync。

原六settings与已配置账号根不静默改变。新环境Python与旧settings不同，明确 `dependency_binding_migration_required`，由既有已审迁移另门处理。新机未有合法绑定明确 `dependency_binding_required`；不能复制Owner账号/profile作模板。没有依赖描述文件保持旧安装行为，仍会明确缺已有SDK/Python/绑定。

测试：`/usr/bin/python3 -B -m unittest test_pro_dependencies test_pro_dependency_process test_pro_dependency_installer`；打包整合另需显式 `CROWD_PARTICIPANT_EXTENSION`（已审own EXT ZIP）和 `CROWD_PARTICIPANT_HELPER`（已审universal/helper）后运行 `test_pro_dependency_package`，缺输入fail而非skip。原 `test_participant_package.py` / `test_participant_existing_chain.py` 保持，嵌套zip/脚本SHA必须完整。普通93通道及原安装绑定不因构建此包改变。

源码依据为已购官方本地项目，Pro-Python d32dd565277116ba4880c28ccd417a7c376cb62d / SignSrv26c53d8f3221d95e0d4961b0593debd179d3cf10，各自README推荐uv sync。许可证为非商业学习使用1.1；未经书面同意不得商用，购买不自动证明向普通参与者再分发私源码的权利。本安装器仅消费本设备已有合法工件；团队/OEM/私有发行授权尚须厂商确认，不自造下载渠道。
