# 安全与依赖审计

## 当前状态

**只对独立 CPU/媒体依赖提供了当前审计通过的锁文件；历史 GPU 模型环境仍有已知漏洞，未完成安全迁移。** 不要把 CI 绿色状态理解为整个机器人、驱动或模型栈的安全认证。

2026-10-25 的范围、原始扫描结果、残留问题和验证记录见 [审计报告](security/audit-2026-10-25.md)。公开仓库内没有历史 GPU 实例的完整 `pip freeze`，因此报告区分“日志证实的版本”和“固定上游声明”，不猜测未知版本。

## 现在应如何使用

- 标准库快速检查仍可独立运行。
- CPU 图像、数据和媒体工具使用 Python 3.12 的 [锁文件](requirements/cpu.txt)。不要把它安装到 Isaac 或旧 StreamVLN Python 中。
- 旧 Python 3.9 / Transformers 4.45.1 记录仅用于理解历史实验，**不是新的推荐安装配置**。不要用于联网服务、加载未知来源文件或处理不可信输入。
- 模型入口仅接受已下载的本地 safetensors；拒绝 bin-only adapter、缺失分片、越界索引和越界 symlink。不会自动反序列化或转换旧 `.bin` 权重。
- 基座/视觉目录不得混入 `adapter_config.json`；训练时配置中的视觉塔绝对路径必须与 `--vision` 指向同一目录，否则拒绝执行。旧配置需要单独迁移，不会自动改写原始模型配置。
- 从可信来源获取模型和源码，核对 revision 与文件哈希；加载时目录必须不可被其他进程修改。safetensors 和离线选项不是沙箱，也不会修复所有依赖漏洞。
- HTTP 适配器保持本机回环监听，不开放到公网。外部 StreamVLN 源码是直接导入执行的代码，需要独立审查。

## 复查 CPU 依赖

从仓库根目录执行；`python3.12` 应来自受维护的 Python 安装：

```bash
python3.12 -m venv .venv-audit
.venv-audit/bin/python -m pip install --require-hashes -r requirements/audit.txt
.venv-audit/bin/pip-audit --strict --disable-pip --require-hashes -r requirements/cpu.txt
.venv-audit/bin/pip-audit --strict --disable-pip --require-hashes -r requirements/audit.txt

python3.12 -m venv .venv-cpu
.venv-cpu/bin/python -m pip install --require-hashes -r requirements/cpu.txt
.venv-cpu/bin/python -m pip check
```

所有传递依赖都在锁文件内；`--disable-pip` 只禁止审计阶段安装/执行依赖，不是跳过锁中的包。安装时另外验证下载哈希与依赖一致性。这里没有 `--ignore-vuln`、`continue-on-error` 或把审计失败转为成功的逻辑。漏洞数据库查询故障也应视为未完成审计。

[GitHub Actions](.github/workflows/dependency-audit.yml) 在 push、PR 和手动触发时运行 CPU/审计器依赖扫描、哈希安装和 CPU 回归测试；不包含付费 GPU 任务。审计器与运行环境分开安装。更新依赖时重新生成完整锁文件、重新审计和验证，不手工删掉传递依赖。

## 未覆盖的边界

pip-audit 检查的是 Python 分发包的已公布漏洞，不等于源码审计或可利用性证明。未覆盖 CUDA/驱动、Isaac/Kit/Omniverse、FFmpeg/ffprobe、Tesseract、OpenCV 等 wheel 内原生库的独立 SBOM、模型权重内容、所有 Git/VCS 依赖及历史 Release 归档。需要相应供应商更新、资产清单和专项检查。

## 报告问题

请勿在公开 issue 中上传密码、token、私有资产或可直接用于攻击的材料。若仓库提供 GitHub 私密漏洞报告入口，请使用该入口；否则先以不包含敏感细节的 issue 请求私密联系渠道。普通依赖版本问题可附包名、版本、公告链接和最小复现条件。
