# 纪录片工具链的依赖审计

核验日期：2026-10-26（中国标准时间）。这份报告仅覆盖 `documentary/` 的 Node 工具链，不替代 Python 模型栈审计，也不代表整个项目不存在安全问题。

## 本轮修复与证据

| 项目 | 修复前 | 修复后 |
| --- | --- | --- |
| npm 可解析依赖中的 Zod | 4.5.4 | 4.6.6，精确 overrides |
| `npm audit --json` | 10 项 high（同一根因及依赖传播） | 0 项已知告警 |
| Remotion 系列 | 4.0.538 | 仍统一为 4.0.538 |
| `@remotion/media` | 间接依赖 | 4.0.538 直接依赖 |
| 有界数组回归 | 越界输入仍访问 3 个元素 | 提前拒绝，访问 0 个元素 |
| Studio 监听 | 通配地址 | 专用启动器固定为 IPv4 loopback |

原始 npm 报告保存在 [修复前](npm-audit.before.json) 与 [修复后](npm-audit.after.json)，包含锁文件 SHA-256 和退出码。未采用 `npm audit fix --force` 建议的 Remotion 回退。初始依赖与 Studio 启动器检查通过 7 项；加入本机导出启动器后，`node --test security/*.test.mjs` 共 9 项均通过。`verification.json` 保留初始检查时点；完整样片验收另列于 `evidence/`。

根因公告为 [GHSA-mrhx-c7xc-m3w5](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5)。[Zod 4.6.6 发布记录](https://github.com/colinhacks/zod/releases/tag/v4.6.6)列出有界集合解析的修复。已核对 Remotion 使用的 `zod/mini`、`zod/v3` 入口在新版本中存在，并验证基本解析行为。

## 仍未修复：预打包代码中的旧 Zod

**npm audit 为 0，不等于本轮完成了全部漏洞修复。**

Remotion 4.0.538 的 6 个 JavaScript 分发文件仍内嵌 Zod 4.5.4 的解析实现，涉及 `studio-protocol`、`codemods` 和 Studio。npm overrides 只替换依赖解析结果，不能改写已打包的代码。文件路径与哈希见 [embedded-zod.json](embedded-zod.json)。这些文件没有被擅自修改，本轮不声称已消除这部分风险，也未证明每个入口的实际可利用性。

后续需要上游重新发布安全版本，或经过独立审查的可重复重建与完整回归，才能关闭这个问题。当前 Studio 仅用于本机、可信素材的预览：不要转发端口，不要暴露到局域网或公网，不要导入不可信的 Studio payload、模板或插件。Loopback 限制缩小暴露面，不是漏洞修复，也不能防御所有本机或浏览器来源的攻击。

## 本机启动

```sh
npm ci --ignore-scripts
npm run dev -- --no-open --port=3117
```

务必通过 `npm run dev` 启动。直接执行 `npx remotion studio` 不使用本项目的监听保护。4.0.538 的 `--ipv4` 只改变地址族，仍会绑定通配地址；并不存在可用的 `--host` 参数。

`security/loopback-studio.cjs` 在当前进程中替换内部端口配置，不改 `node_modules` 文件。启动前断言 Remotion 版本为 4.0.538，升级后需要人工复查。实际启动验收确认监听为 `127.0.0.1`，并成功获取预览页面；测试实例已经停止。导出与抽帧也使用共享该限制的 `security/loopback-render.cjs`，只允许 `render`、`still`、`compositions` 三种本机命令。Remotion 的日志仍可能打印 Network URL，该文本不代表实际监听地址，应以系统 socket 检查为准。

Remotion CLI 会提示 Zod 版本与其推荐的 4.5.4 不同。这是本轮安全覆盖的预期警告，不应照提示回退到有公告的旧版本；目前验证仅覆盖本项目使用的预览路径，不保证所有 Remotion 可选功能。

## 复查命令

```sh
node --test security/*.test.mjs
node security/capture-audit.mjs after
node security/scan-embedded-zod.mjs
npm ls zod @remotion/media remotion @remotion/cli --all
npx tsc --noEmit
npm run lint
```

扫描脚本输出的是残余清单，不是“安全通过”认证。重新运行会刷新报告日期与哈希。npm 公告数据随时间变化，网络错误不能视作零告警。

## 许可证边界

项目原创源代码的许可范围遵循根目录 [LICENSE](../../LICENSE) 与 [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md)。这不改变任何依赖或素材的权利。

Remotion 核心、CLI 及部分模块采用 **Remotion License，不是 MIT**；部分独立包采用 MIT，也不能据此把整个 Remotion 工具链标为 MIT。使用者应按[官方许可说明](https://www.remotion.dev/docs/license)及所安装版本的 `LICENSE.md` 判断是否需要商业许可。本项目未购买或转授 Remotion 商业许可证，也不承诺任何组织自动符合免费资格。原始媒体、模型权重、第三方资产与项目源码许可分别处理。
