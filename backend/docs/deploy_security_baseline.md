# 公网部署安全基线检查表

## 传输与访问

- [ ] 强制 HTTPS/TLS：反向代理或负载均衡终止 SSL，后端仅监听内网或 localhost。
- [ ] 限制跨域与来源：CORS 仅允许前端域名；必要时校验 Origin/Referer。
- [ ] 限流与防滥用：对登录、上传、导出、LLM 接口做频率限制。

## 配置与密钥

- [ ] 敏感配置与密钥使用托管平台 Secret/KMS 管理，禁止写入代码或明文配置文件。
- [ ] 生产环境设置 `ENCRYPTION_KEY`、`JWT_SECRET` 等为强随机值并通过环境或 Secret 注入。
- [ ] `DEBUG=false`，`APP_ENV=production`。

## 数据与审计

- [ ] 存储加密已启用（`ENCRYPTION_ENABLED=true`），合同与敏感字段加密落库。
- [ ] 审计日志保留 1 年，定时任务执行 `python -m app.tasks.retention` 做过期清理。
- [ ] 审计导出接口仅对已认证用户开放，且仅可导出自身数据。

## 应用与依赖

- [ ] 依赖无已知高危漏洞（定期 `pip audit` 或等同检查）。
- [ ] 容器或进程以非 root 用户运行；文件权限最小化。
