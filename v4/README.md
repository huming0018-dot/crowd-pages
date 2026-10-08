# v4 私有 Mac 分发

先从 canonical `crawler-extension/v4` 构建，再生成安装包：

```sh
python3 v4/test_release.py /path/to/crawler-extension/v4
python3 v4/build_trial.py --source /private/crowd-extension.zip \
  --invitation-file /private/mac-trial.json --output /private/Mac轻量内测.zip
```

构建器验证源协议、版本、worker与所有文件摘要，注入仍有效的原私有邀请，重新生成交付摘要。说明页版本自动取自客户端 manifest。包内 `release.json` 与旁边 `.sha256` 是产物事实；当前验收状态统一见 crowd-kol/docs/V4_ITERATION.md。

更新助手沿用原 v4 目录。本人必须在原浏览器刷新扩展并核对版本；不能静默授权。保留原个人资料、插件目录与参与身份，不要卸载重报。不要加载到原生产v3个人资料，两条协议共享历史扩展ID但身份不同。

本工具不报名、不扩容邀请、不发布 Pages/CRX、不变更 updates.xml。私人邀请及安装ZIP禁止提交或上传公开Release。真实Mac采集尚须验收。
