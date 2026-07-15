# 策维 v1.10 单用户云同步说明

## 定位

本功能服务于自用设备，不建设账号中心，不提供注册、找回密码、用户资料或多租户管理界面。用户只看到“同步密码”。底层使用一个固定内部账号完成 Supabase 身份验证。

## 初始化

1. 打开 Supabase 项目的 SQL Editor，执行 `supabase/setup.sql`。
2. 打开 Authentication > Users，新增用户 `ceway-sync@ceway.local`。
3. 设置至少 8 位同步密码，并将用户标记为已确认。
4. 在策维的 DLT 或 SSQ 页面进入“云端同步”，输入该密码连接。

## 同步范围

- 大乐透保存方案与历史记录。
- 双色球保存方案与历史记录。
- 多设备记录按记录 ID 合并，最多保留每个场景最近 100 条。
- 本地数据始终保留；断开设备只清理本机登录会话，不删除云端数据。

## 安全边界

- 前端仅使用 Supabase publishable key。
- `ceway_sync_state` 已启用 RLS，认证用户只能读写 `user_id = auth.uid()` 的数据。
- 禁止将 secret key 或 service role key写入前端、Git 仓库或公开日志。
- 同步方案用于跨设备保存，不改变号码评分、推荐公式或中奖概率。
