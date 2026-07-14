# Open Session 兼容性核验（2026-07-14）

## 观察到的入口

已打开 Open Session 首页并读取可见页面结构。页面将任务分成四类 leaderboard：

- Instruction Following
- Robustness
- Spatial Reasoning
- Manipulation

页面的提交说明是上传/部署机器人模型，由平台自动运行 benchmark；入口没有
`/v1/episodes/reset`、`/step`、`/close`，也没有接收 StreamVLN
`annotations.json`、RGB/depth sidecar、GenieSim 轨迹或本地 `eval_result.json` 的
字段。换句话说，当前页面是模型部署型评测，不是本实验的 episode 控制协议。

## 登录与副作用边界

使用用户已提供的账号尝试登录后，页面按钮持续显示 `Signing in...`，约 18 秒内
没有建立可确认的会话，也没有出现提交表单或提交成功回执。没有上传模型、创建
任务、提交榜单或触发任何外部评测。

## 结论

本项目继续遵守“不向 AgiBot Open Session 榜单提交”的计划约束。若未来要提交，
需要先获得平台要求的模型部署/容器接口和任务映射；不能把本地 StreamVLN
annotations 或 GenieSim HTTP episode 直接伪装成 Open Session 模型提交。
