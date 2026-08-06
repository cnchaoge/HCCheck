# HCCheck v1.2.4 (2026-08-06)

## 🎉 新功能

### machine_id 远程白名单 (TOFU 模式)
- **新机制**: 任何机器首次跑 → 自动进白名单 → 通过
- 服务器后台可"撤销"特定机器 (5 分钟内 cache 失效后 fail-closed)
- 服务器后台可"设为过期"全局封禁 (即时生效)
- 离线缓存 5 分钟 TTL (断网时用上次结果, 避免假阳性)

### license-admin 网页 (腾讯云 server)
- 改 license.json / 模拟过期 / 恢复 / 撤销机器 / 批准 pending
- URL: http://82.156.229.67/license-admin/ (admin / 密码见 MEMORY)
- 配套 4 个 API: `/license-api/{check,grant,revoke,machines}`

## 🔧 修复

- **run.py:1521** 仍写死 `channel="chrome"`, 需要系统装 Google Chrome
- **v1.2.3 已知 bug**: `run.py main()` 缺 `force=True` 检查 (只 GUI 入口有), 启动时不会验证 license

## ⚠️ 部署注意

- **运管站电脑必须装 Google Chrome** (exe 不带浏览器)
- 老电脑已有 Chrome, 新电脑跑前: `winget install Google.Chrome`
- UKey 驱动需单独装 (不在 exe 里)

## 📦 文件清单

- `HCCheck.exe` (~38MB, 单文件, Windows 10/11 x64)
- 配套源码: `git archive --format=zip --output hccheck-v1.2.4.zip HEAD`
- 服务器端: 已在 82.156.229.67 部署 (Flask + nginx + systemd)

## 🔐 安全机制

1. **fail-closed**: 网络挂 / 解析失败 / 过期 / 未授权 → 抛伪装 RuntimeError
2. **反破解 5+1 点**: 错误信息伪装成 "unexpected EOF when parsing JSON", 不暴露 "license" / "授权" 关键词
3. **machine_id = sha256(MAC + hostname)[:16]**: 改 MAC/hostname 5 分钟可绕过 (简单版)
4. **离线缓存**: 防断网时假阳性
5. **TOFU + revoked 列表**: 撤销过的机器永不复用自动批准

## 📝 完整 Changelog

详见 git log (commit `0a50cef` 起)
