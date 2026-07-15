# Supabase 初始化

1. 在 SQL Editor 执行 `setup.sql`。
2. 在 Authentication > Users 创建并确认 `ceway-sync@ceway.local`。
3. 使用自设的至少 8 位密码，不需要向代码或仓库写入密码。

应用使用公开 publishable key，并依赖 `ceway_sync_state` 的 RLS 策略保护数据。不要在本目录保存 secret key 或 service role key。
