# 集成/迁移步骤

1. **仓库侦察**
   - 确认真实 domain/API/web/db 路径。
   - 确认数据库是 PostgreSQL 还是当前开发环境替代方案。
   - 确认 Alembic 与测试夹具。

2. **纯 domain 首先落地**
   - 类型、玩法校验、金额、bitmask、collision profile。
   - 先跑 reference tests；不接 DB/UI。

3. **DB migration**
   - 将 `DB_SCHEMA.sql` 翻译成现有 SQLAlchemy models + 可逆 Alembic。
   - 不直接执行裸 SQL 建表作为最终实现。

4. **数据导入**
   - CSV adapter + 质量门禁。
   - 号码非法/重复/期号重复必须拒绝或隔离。

5. **Service/API**
   - runs、generate、collision analyze、freeze、settle。

6. **前端**
   - 先做 random/bet calculator + collision explorer。
   - 再做 model generator/package/freeze compare。

7. **历史数据接入**
   - 若已有大乐透 Excel/CSV 资产，写一次性 importer；保留 source/checksum/imported_at。

8. **性能优化**
   - 先 bitmask + Python int.bit_count。
   - 如 7,920~数十万候选仍慢，再做 NumPy/Polars/vectorization/worker；不要过早分布式。

9. **验收**
   - 执行 `tests/ACCEPTANCE_TESTS.md`。
   - 运行全仓 lint/typecheck/test/e2e。
