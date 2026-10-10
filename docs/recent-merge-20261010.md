# 动态展示合并修复 · 2026-10-10

状态：两个仓库已合并 main；公开页已实际发布，后台服务器部署受连接阻塞尚未完成。
更新人：Codex；时间：2026-10-10（Asia/Shanghai）。

## 问题与范围
倒序下的负时间差使相隔 60 分钟的同店同人同状态记录错误合并。
此问题只发生在展示层；本修复不修改生产采集记录、统计 RPC、数据库函数或查询。
动态 ×N 表示当前 recent 样本内的记录数，不代表独立信封提交数，也不应解释为漏采。

## 已核验的后端合同
通过线上只读 pg_get_functiondef 核验 public.crowd_status_summary()：
从 crowd_proofs 按 id DESC 取最近 10 行，jsonb_agg 同样按 id DESC。
与 crowd-kol/main/server/crowd/sql/crowd_fix_v330_status.sql 一致。
内部 /api/monitor 直接代理此 RPC，不重排。
因此 id 顺序是取样合同，不保证 created_at 严格倒序；前端只对副本按时间倒序展示。

## 两处共用规则 v1
crowd-pages/status.html 与 kimi-workspace/workspace/food-cloud-v2/admin.py
在 BEGIN/END crowd recent merge v1 标记之间使用字节一致的纯 JS 函数。
保持两处自包含部署，避免引入跨站运行时依赖。
后续修改必须同时同步这段函数，并对两份真实源码执行回归。

1. 不修改原数组；按可解析的 created_at 倒序排列，无效时间放末尾，同时间保留 API 原顺序。
2. 只合并显示顺序中的相邻组：非空店铺名、完整参与者 ID、非空状态均须一致。
3. 固定组内最新记录为锚：0 <= 最新时间 - 当前时间 < 600000 ms。
4. 恰好 10 分钟不合并（沿用原严格小于边界）；跨午夜按绝对时间差处理。
5. 无效时间或未知身份不合并；参与者 ID 截短仅用于显示。
6. 合并只增加 n，显示时间保留最新记录；连续小间隔不能滚动扩展窗口。
7. 同名店铺仍按 matched_store 口径，RPC 未提供店铺唯一 ID；不扩展本次范围。

## 验证
Node.js 无外部依赖、无真实网络、无后台 import：
每处 40 项检查，共 80 项；两段函数的字节一致性同时校验。
覆盖正序/倒序 2、10、60 分钟，边界前后，跨日，时区等价，完整 ID 同前缀碰撞，
不同参与者/店铺/状态，无效时间，缺失身份，乱序，同时间，中间插入其他店，
以及 0/8/16 分钟链式扩窗反例。
真实页面脚本语法、真实 load/loadMonitor + stub DOM/RPC 渲染回归通过；
admin.py 的 Python 编译通过。原样本不变且合并后 n 总和保持一致。

运行：
```bash
node tests/recent_merge.test.cjs
# 同时持有两仓库时，在共同父目录核验口径：
node crowd-pages/tests/recent_merge.test.cjs crowd-pages/status.html kimi-workspace/workspace/food-cloud-v2/admin.py
```

## 发布
公开页：合并 crowd-pages/main 后检查 GitHub Pages 构建和线上 status.html 的新规则。
内部后台：合并 kimi-workspace/main 后，将 admin.py 同步至 /home/ubuntu/food-cloud-v2/admin.py，
先备份、编译，再重启 food-admin；核验实际 HTML 包含新函数。
禁止把 main 合并写成后台已发布；未取得服务器发布通道时明确记录阻塞。

## 本次发布核验
- crowd-pages PR #2 已合并：a7b80449a5efbcda704a2208ec3f617a61a42742。
- kimi-workspace PR #1 已合并：517adcb63a06dbd08c71421b97246d2c0b910dc1。
- 两处 main 源码与本地通过回归的内容逐字一致；两仓库 GitHub Actions samples 均 success。
- 已从 https://huming0018-dot.github.io/crowd-pages/status.html 抓取实际线上 HTML，并与后台 main 规则同时重跑：80 checks PASS。公开页新规则已可访问。
- 后台 / 返回令牌门页，不能凭匿名响应核验监控 HTML。DevSpace 的 ~/Documents/kimi 和 /Users/hubowen/Documents/kimi 两次均 Internal error，当前执行环境未持有 ~/.ssh/food_cloud_deploy；没有可用服务器发布通道。本次未更新服务器文件、未重启服务，禁止将后台 main 合并误报为上线。
- 剩余：恢复已有可 SSH 终端后，仅备份/同步 /home/ubuntu/food-cloud-v2/admin.py，编译并重启 food-admin，核验真实响应。无需再次授权合并/发布。
