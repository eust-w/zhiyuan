import type { CSSProperties, ReactNode } from "react";
import { Video } from "@remotion/media";
import {
  AbsoluteFill,
  CanvasImage,
  Interactive,
  Sequence,
  Track,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import sample from "../content/sample.json";
import facts from "./generated/facts.json";
import {
  pairedProjection,
  stateAtStep,
  stepForFrame,
  type Episode,
} from "./visual-model";

const color = {
  paper: "#F2F0E8",
  ink: "#1D2528",
  muted: "#687173",
  teal: "#136E63",
  line: "#C9CEC7",
  white: "#FFFDF7",
};
const font = "PingFang SC, Noto Sans CJK SC, Microsoft YaHei, sans-serif";
const mono = "SFMono-Regular, Menlo, monospace";
const segment = (id: string) => {
  const found = sample.segments.find((item) => item.id === id);
  if (!found) throw new Error(`Missing storyboard segment: ${id}`);
  return found;
};
const media = (id: string) => {
  const path = segment(id).source.mediaPath;
  if (!path) throw new Error(`Missing source media: ${id}`);
  return staticFile(path);
};

const Entrance = ({
  children,
  delay = 0,
  style,
}: {
  children: ReactNode;
  delay?: number;
  style?: CSSProperties;
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <div
      style={{
        ...style,
        opacity: interpolate(
          frame,
          [delay * fps, (delay + 0.65) * fps],
          [0, 1],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
        ),
        translate: interpolate(
          frame,
          [delay * fps, (delay + 0.8) * fps],
          ["0px 22px", "0px 0px"],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
        ),
      }}
    >
      {children}
    </div>
  );
};

const Header = ({
  chapter,
  evidence,
  dark = false,
}: {
  chapter: string;
  evidence: string;
  dark?: boolean;
}) => (
  <div
    style={{
      position: "absolute",
      left: 96,
      right: 96,
      top: 68,
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
      fontSize: 28,
      color: dark ? color.paper : color.muted,
      letterSpacing: 2,
    }}
  >
    <span>
      GENIESIM × STREAMVLN{" "}
      <span style={{ opacity: 0.55, padding: "0 20px" }}>／</span>
      {chapter}
    </span>
    <span
      style={{
        fontSize: 25,
        borderBottom: `1px solid ${dark ? "#7A8584" : color.line}`,
        paddingBottom: 10,
      }}
    >
      {evidence}
    </span>
  </div>
);

const Footer = ({ dark = false }: { dark?: boolean }) => (
  <div
    style={{
      position: "absolute",
      left: 96,
      right: 96,
      bottom: 38,
      display: "flex",
      justifyContent: "space-between",
      fontSize: 24,
      color: dark ? "#CCD2CD" : color.muted,
      borderTop: `1px solid ${dark ? "#57615D" : color.line}`,
      paddingTop: 18,
    }}
  >
    <span>视觉样片 · 配音待确认</span>
    <span>非官方等价适配 · 历史证据与当前验证分开呈现</span>
  </div>
);

const Scene = ({
  children,
  chapter,
  evidence,
  dark = false,
}: {
  children: ReactNode;
  chapter: string;
  evidence: string;
  dark?: boolean;
}) => (
  <AbsoluteFill
    style={{
      fontFamily: font,
      background: dark ? color.ink : color.paper,
      color: dark ? color.paper : color.ink,
    }}
  >
    {children}
    <Header chapter={chapter} evidence={evidence} dark={dark} />
    <Footer dark={dark} />
  </AbsoluteFill>
);

const Opening = () => (
  <Scene chapter="从一个问题开始" evidence="真实 RGB 数据回放" dark>
    <Video
      name="开场相机源片"
      src={media("opening")}
      muted
      objectFit="contain"
      style={{ width: "100%", height: "100%" }}
    />
    <AbsoluteFill
      style={{
        background:
          "linear-gradient(90deg, rgba(19,27,28,0.92) 0%, rgba(19,27,28,0.67) 35%, rgba(19,27,28,0.08) 75%), linear-gradient(0deg, rgba(19,27,28,0.9), transparent 25%, transparent 82%, rgba(19,27,28,0.9))",
      }}
    />
    <Entrance style={{ position: "absolute", left: 96, top: 272 }}>
      <div
        style={{
          fontSize: 38,
          letterSpacing: 8,
          color: "#AECAC2",
          marginBottom: 34,
        }}
      >
        看见 · 行动 · 验证
      </div>
      <Interactive.H1
        name="片名"
        style={{
          margin: 0,
          fontSize: 138,
          lineHeight: 1.15,
          fontWeight: 650,
          letterSpacing: -4,
        }}
      >
        机器人
        <br />
        走起来之后
      </Interactive.H1>
    </Entrance>
    <Entrance delay={3.2} style={{ position: "absolute", left: 102, top: 722 }}>
      <div style={{ fontSize: 45, color: "#E3E8DF" }}>
        它真的知道，目标在哪里吗？
      </div>
    </Entrance>
    <div
      style={{
        position: "absolute",
        right: 98,
        bottom: 140,
        fontSize: 25,
        color: color.paper,
        textAlign: "right",
        lineHeight: 1.7,
      }}
    >
      头部相机 · 基础模型
      <br />
      <span style={{ fontFamily: mono }}>
        {segment("opening").source.episodeId}
      </span>
      <br />
      动作帧回放，非实时桌面录屏
    </div>
  </Scene>
);

const LoopDiagram = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const progress = interpolate(frame, [fps, 8.7 * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const nodes = [
    { x: 150, label: "画面", detail: "头部相机 RGB" },
    { x: 660, label: "判断", detail: "StreamVLN + 历史" },
    { x: 1170, label: "动作", detail: "GenieSim 执行" },
  ];
  return (
    <div
      style={{
        position: "absolute",
        left: 96,
        top: 350,
        width: 1728,
        height: 440,
      }}
    >
      <svg width="1728" height="440" style={{ position: "absolute", inset: 0 }}>
        <path
          d="M280 116 H 1450 V 360 H 280 V 116"
          stroke={color.line}
          strokeWidth="2"
          fill="none"
        />
        <path
          d="M280 116 H 1450 V 360 H 280 V 116"
          pathLength="1"
          stroke={color.teal}
          strokeWidth="5"
          fill="none"
          strokeDasharray={`${progress} 1`}
          strokeLinecap="round"
        />
        <path
          d="M600 103 L620 116 L600 129 M1110 103 L1130 116 L1110 129"
          fill="none"
          stroke={color.teal}
          strokeWidth="4"
        />
      </svg>
      {nodes.map((node, index) => (
        <div
          key={node.label}
          style={{
            position: "absolute",
            left: node.x,
            top: 25,
            width: 330,
            background: color.paper,
            padding: "25px 0 10px",
            opacity: interpolate(
              frame,
              [index * 1.5 * fps, (index * 1.5 + 0.6) * fps],
              [0.2, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            ),
          }}
        >
          <div style={{ fontSize: 80, fontWeight: 600, marginBottom: 30 }}>
            {node.label}
          </div>
          <div style={{ fontSize: 31, color: color.muted }}>{node.detail}</div>
        </div>
      ))}
      <div
        style={{
          position: "absolute",
          top: 324,
          left: 575,
          width: 530,
          textAlign: "center",
          background: color.paper,
          fontSize: 34,
          color: color.teal,
        }}
      >
        新画面，进入下一轮判断
      </div>
    </div>
  );
};

const ClosedLoop = () => (
  <Scene chapter="闭环" evidence="示意动画 · 解释实际流程">
    <Entrance style={{ position: "absolute", left: 96, top: 169 }}>
      <h2
        style={{ fontSize: 92, lineHeight: 1.15, margin: 0, fontWeight: 600 }}
      >
        看图，行动，再看图。
      </h2>
    </Entrance>
    <LoopDiagram />
    <Entrance
      delay={5.4}
      style={{
        position: "absolute",
        left: 130,
        top: 831,
        fontSize: 36,
        color: color.muted,
      }}
    >
      动作不是预先写好的路线。
      <span style={{ color: color.ink }}>每一轮，都要接住模型的输出。</span>
    </Entrance>
  </Scene>
);

const DatasetFields = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const fields = [
    { key: "rgb", label: "这一刻，看到了什么" },
    { key: "action", label: "接下来，执行了什么" },
    { key: "depth / pose", label: "空间与位姿，是否对齐" },
    { key: "distance / blocked", label: "距目标多远，是否被拦截" },
  ];
  return (
    <div style={{ position: "absolute", left: 1150, top: 330, width: 660 }}>
      {fields.map((field, i) => (
        <div
          key={field.key}
          style={{
            padding: "22px 0",
            borderBottom: `1px solid ${color.line}`,
            opacity: interpolate(
              frame,
              [i * 1.8 * fps, (i * 1.8 + 0.7) * fps],
              [0.25, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            ),
          }}
        >
          <div
            style={{
              fontSize: 32,
              fontFamily: mono,
              color: color.teal,
              marginBottom: 12,
            }}
          >
            {field.key}
          </div>
          <div style={{ fontSize: 33 }}>{field.label}</div>
        </div>
      ))}
    </div>
  );
};

const DataDetail = () => (
  <div
    style={{
      width: 980,
      height: 552,
      background: color.ink,
      color: color.paper,
      padding: "52px 56px",
      boxSizing: "border-box",
    }}
  >
    <div style={{ fontSize: 27, color: "#B0C4BC", marginBottom: 30 }}>
      保存方式，决定以后能否核对。
    </div>
    <div style={{ fontFamily: mono, fontSize: 42, lineHeight: 1.8 }}>
      annotations.json
    </div>
    <div style={{ fontSize: 34, color: "#CDD4CB", marginBottom: 36 }}>
      训练所需图像与动作
    </div>
    <div style={{ fontFamily: mono, fontSize: 42, lineHeight: 1.8 }}>
      sidecar
    </div>
    <div style={{ fontSize: 34, color: "#CDD4CB" }}>
      深度、位姿、目标、完整结束记录
    </div>
  </div>
);

const DataStructure = () => {
  const { fps } = useVideoConfig();
  const source = sample.segments.find(
    (item) => item.id === "data-structure",
  )?.replaySource;
  if (!source?.mediaPath) throw new Error("Missing training replay source");
  return (
    <Scene chapter="数据" evidence="真实数据回放 + 数据结构示意">
      <Entrance style={{ position: "absolute", left: 96, top: 170 }}>
        <h2 style={{ fontSize: 88, margin: 0, fontWeight: 600 }}>
          每一步，都留下证据。
        </h2>
      </Entrance>
      <Sequence
        name="单条训练轨迹回放"
        durationInFrames={9 * fps}
        layout="none"
      >
        <div style={{ position: "absolute", left: 96, top: 326 }}>
          <Video
            name="训练轨迹源片"
            src={staticFile(source.mediaPath)}
            muted
            objectFit="contain"
            style={{ width: 980, height: 552, background: color.ink }}
          />
          <div
            style={{
              position: "absolute",
              left: 28,
              bottom: 24,
              padding: "10px 16px",
              background: "#1D2528E6",
              color: color.paper,
              fontSize: 24,
            }}
          >
            真实训练轨迹回放 · 不循环片段
          </div>
        </div>
      </Sequence>
      <Sequence
        name="数据记录结构详解"
        from={9 * fps}
        durationInFrames={3 * fps}
        layout="none"
      >
        <div style={{ position: "absolute", left: 96, top: 326 }}>
          <DataDetail />
        </div>
      </Sequence>
      <DatasetFields />
      <div style={{ position: "absolute", left: 1150, top: 924, fontSize: 32 }}>
        <span style={{ color: color.teal, fontWeight: 650 }}>
          {facts.training.episodes}
        </span>{" "}
        条训练 <span style={{ padding: "0 16px", color: color.line }}>／</span>
        <span style={{ fontWeight: 650 }}>
          {facts.historical.episodes}
        </span>{" "}
        条留出评测
      </div>
    </Scene>
  );
};

const TrainingDetail = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const late = frame >= 6 * fps;
  return (
    <div style={{ position: "absolute", left: 1290, top: 340, width: 510 }}>
      <div style={{ fontSize: 29, color: color.muted, marginBottom: 12 }}>
        历史训练 · 更新步数
      </div>
      <div style={{ fontSize: 132, letterSpacing: -5, lineHeight: 1.1 }}>
        {facts.training.updates}
      </div>
      <div style={{ height: 1, background: color.line, margin: "40px 0" }} />
      <div style={{ fontSize: 29, color: color.muted, marginBottom: 20 }}>
        首末记录损失
      </div>
      <div style={{ fontSize: 50, fontFamily: mono }}>
        {facts.training.lossFirst} <span style={{ color: color.teal }}>→</span>
      </div>
      <div style={{ fontSize: 66, fontFamily: mono, color: color.teal }}>
        {facts.training.lossLast}
      </div>
      <div
        style={{
          marginTop: 42,
          fontSize: 33,
          lineHeight: 1.55,
          color: late ? color.ink : color.muted,
        }}
      >
        {late ? (
          <>
            拟合变化是真的。
            <br />
            导航能力，还要另测。
          </>
        ) : (
          <>
            这是训练结果，
            <br />
            不是导航成功率。
          </>
        )}
      </div>
    </div>
  );
};

const Training = () => (
  <Scene chapter="训练" evidence="真实结果图 · 原训练曲线">
    <Entrance style={{ position: "absolute", left: 96, top: 170 }}>
      <h2 style={{ fontSize: 88, margin: 0, fontWeight: 600 }}>
        损失下降，意味着什么？
      </h2>
    </Entrance>
    <div
      style={{
        position: "absolute",
        left: 96,
        top: 326,
        width: 1100,
        height: 565,
        background: color.white,
        display: "flex",
        alignItems: "center",
      }}
    >
      <CanvasImage
        name="原训练曲线截图"
        src={media("training")}
        style={{ width: "100%", height: "100%", objectFit: "contain" }}
      />
    </div>
    <TrainingDetail />
  </Scene>
);

const baseEpisode = facts.historical.base.episodes.find(
  (item) => item.id === segment("paired-replay").pairEpisodeId,
);
const loraEpisode = facts.historical.lora.episodes.find(
  (item) => item.id === segment("paired-replay").pairEpisodeId,
);
if (!baseEpisode || !loraEpisode)
  throw new Error("Paired episode is not present in verified facts");
const pairedEpisodes = [baseEpisode, loraEpisode];
const projection = pairedProjection(pairedEpisodes, 740, 420, 55);
const pairEndStep = Math.max(baseEpisode.steps, loraEpisode.steps);
const actionName = (actionId: number | null) =>
  actionId === null
    ? "初始状态"
    : (["停止", "前进", "左转", "右转"][actionId] ?? "未知动作");

const TrajectoryPanel = ({
  episode,
  label,
  left,
}: {
  episode: Episode;
  label: string;
  left: number;
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const step = stepForFrame(frame, fps, 16, pairEndStep);
  const state = stateAtStep(episode.trajectory, step);
  const end =
    state.step === episode.trajectory[episode.trajectory.length - 1].step;
  const [x, y] = projection.point(state.xy);
  const [tx, ty] = projection.point(episode.targetXY);
  const points = episode.trajectory
    .filter((point) => point.step <= state.step)
    .map((point) => projection.point(point.xy).join(","))
    .join(" ");
  const arrowX = x + 23 * Math.cos(state.headingRad);
  const arrowY = y - 23 * Math.sin(state.headingRad);
  return (
    <div style={{ position: "absolute", top: 292, left, width: 830 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          padding: "0 38px 18px",
        }}
      >
        <span style={{ fontSize: 48, fontWeight: 600 }}>{label}</span>
        <span style={{ fontSize: 26, color: color.muted }}>
          动作步 {state.step} / {episode.steps}
        </span>
      </div>
      <svg
        width="830"
        height="470"
        viewBox="0 0 740 420"
        style={{ background: color.white }}
      >
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <line
            key={`x${i}`}
            x1={i * 100}
            x2={i * 100}
            y1="22"
            y2="398"
            stroke="#E5E8E1"
            strokeWidth="1"
          />
        ))}
        {[1, 2, 3, 4].map((i) => (
          <line
            key={`y${i}`}
            x1="22"
            x2="718"
            y1={i * 100}
            y2={i * 100}
            stroke="#E5E8E1"
            strokeWidth="1"
          />
        ))}
        <circle
          cx={tx}
          cy={ty}
          r={projection.radius(facts.historical.successRadiusM)}
          fill="#136E630B"
          stroke={color.teal}
          strokeWidth="1.5"
          strokeDasharray="5 5"
        />
        <circle cx={tx} cy={ty} r="7" fill="#A83F32" />
        <text
          x={tx + 14}
          y={ty - 12}
          fill={color.ink}
          fontFamily={font}
          fontSize="22"
        >
          目标
        </text>
        <polyline
          points={points}
          fill="none"
          stroke={color.teal}
          strokeWidth="4"
          strokeLinejoin="round"
        />
        <circle
          cx={projection.point(episode.trajectory[0].xy)[0]}
          cy={projection.point(episode.trajectory[0].xy)[1]}
          r="7"
          fill={color.white}
          stroke={color.ink}
          strokeWidth="2"
        />
        <line
          x1={x}
          y1={y}
          x2={arrowX}
          y2={arrowY}
          stroke={color.ink}
          strokeWidth="5"
          strokeLinecap="round"
        />
        <circle cx={x} cy={y} r="8" fill={color.teal} />
      </svg>
      <div
        style={{
          padding: "20px 28px",
          display: "flex",
          justifyContent: "space-between",
          fontSize: 31,
        }}
      >
        <span>
          距目标{" "}
          <strong style={{ fontWeight: 600 }}>
            {state.distanceM.toFixed(2)} m
          </strong>
        </span>
        <span style={{ color: state.blocked ? "#A83F32" : color.teal }}>
          {end
            ? "轨迹已结束"
            : `${actionName(state.actionId)}${state.blocked ? " · 被拦截" : ""}`}
        </span>
      </div>
    </div>
  );
};

const PairedReplay = () => (
  <Scene chapter="配对评测" evidence="真实轨迹重绘 · 非仿真画面">
    <Entrance style={{ position: "absolute", left: 96, top: 162 }}>
      <h2 style={{ fontSize: 86, margin: 0, fontWeight: 600 }}>
        同一起点，两种选择。
      </h2>
    </Entrance>
    <TrajectoryPanel
      episode={pairedEpisodes[0]}
      label="基础模型 · Base"
      left={96}
    />
    <TrajectoryPanel
      episode={pairedEpisodes[1]}
      label="微调模型 · LoRA"
      left={994}
    />
    <div
      style={{
        position: "absolute",
        left: 110,
        top: 945,
        fontSize: 24,
        color: color.muted,
      }}
    >
      {segment("paired-replay").pairEpisodeId} ·
      按共同动作步同步，短轨迹结束后停留 · 无障碍物底图，不代表墙钟时间
    </div>
  </Scene>
);

const ResultsDetails = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const rows = [
    {
      label: "最终距离 · 均值",
      base: `${facts.historical.base.meanFinalDistanceM.toFixed(2)} m`,
      lora: `${facts.historical.lora.meanFinalDistanceM.toFixed(2)} m`,
    },
    {
      label: "前进安全门拦截",
      base: `${facts.historical.base.blockedForwardCount} 次`,
      lora: `${facts.historical.lora.blockedForwardCount} 次`,
    },
    {
      label: "动作步数 · 均值",
      base: `${facts.historical.base.meanSteps.toFixed(1)} 步`,
      lora: `${facts.historical.lora.meanSteps.toFixed(1)} 步`,
    },
  ];
  return (
    <div style={{ position: "absolute", left: 885, top: 365, width: 915 }}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1.4fr 1fr 1fr",
          fontSize: 29,
          color: "#B4C5BC",
          borderBottom: "1px solid #4B5853",
          paddingBottom: 26,
        }}
      >
        <span>同一批留出评测</span>
        <span>Base</span>
        <span>LoRA</span>
      </div>
      {rows.map((row, i) => (
        <div
          key={row.label}
          style={{
            display: "grid",
            gridTemplateColumns: "1.4fr 1fr 1fr",
            alignItems: "center",
            fontSize: 36,
            borderBottom: "1px solid #4B5853",
            padding: "34px 0",
            opacity: interpolate(
              frame,
              [(i * 1.6 + 0.8) * fps, (i * 1.6 + 1.5) * fps],
              [0.1, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            ),
          }}
        >
          <span style={{ fontSize: 30 }}>{row.label}</span>
          <span>{row.base}</span>
          <span>{row.lora}</span>
        </div>
      ))}
      <div
        style={{
          fontSize: 29,
          lineHeight: 1.7,
          color: "#B4C5BC",
          marginTop: 28,
        }}
      >
        拦截不是实体接触碰撞。
        <br />
        更少的动作，也可能只是更早停止。
      </div>
    </div>
  );
};

const Results = () => (
  <Scene chapter="完整结果" evidence="真实结果图 · 来自评测 JSON" dark>
    <Entrance style={{ position: "absolute", left: 96, top: 162 }}>
      <h2 style={{ fontSize: 86, margin: 0, fontWeight: 600 }}>
        {facts.historical.episodes} 条评测，两者都未到达。
      </h2>
    </Entrance>
    <div style={{ position: "absolute", left: 100, top: 370 }}>
      <div style={{ fontSize: 32, color: "#B4C5BC" }}>Base 与 LoRA</div>
      <div
        style={{
          fontSize: 220,
          letterSpacing: -10,
          lineHeight: 1.1,
          marginTop: 14,
        }}
      >
        {facts.historical.base.successCount}
        <span style={{ fontSize: 95, letterSpacing: -4, color: "#A4B4AB" }}>
          {" "}
          / {facts.historical.episodes}
        </span>
      </div>
      <div style={{ fontSize: 40, marginTop: 30 }}>
        成功半径 {facts.historical.successRadiusM} 米
      </div>
      <div style={{ fontSize: 28, color: "#B4C5BC", marginTop: 25 }}>
        SPL 代理值 {facts.historical.base.splProxy} /{" "}
        {facts.historical.lora.splProxy}
        <br />
        采用初始直线距离，非测地距离
      </div>
    </div>
    <ResultsDetails />
  </Scene>
);

const ChallengeItem = ({
  number,
  title,
  detail,
  top,
  delay,
}: {
  number: string;
  title: string;
  detail: string;
  top: number;
  delay: number;
}) => (
  <Entrance
    delay={delay}
    style={{
      position: "absolute",
      left: 100,
      right: 100,
      top,
      display: "flex",
      alignItems: "baseline",
      gap: 58,
      borderTop: `1px solid ${color.line}`,
      paddingTop: 30,
    }}
  >
    <span style={{ fontSize: 30, fontFamily: mono, color: color.teal }}>
      {number}
    </span>
    <span style={{ fontSize: 58, width: 475, fontWeight: 600 }}>{title}</span>
    <span style={{ fontSize: 34, color: color.muted }}>{detail}</span>
  </Entrance>
);

const Challenge = () => (
  <Scene chapter="可验证的下一步" evidence="研究方向 · 尚未实现">
    <Entrance style={{ position: "absolute", left: 96, top: 162 }}>
      <h2 style={{ fontSize: 86, margin: 0, fontWeight: 600 }}>
        把问题拆小，改进才有落点。
      </h2>
    </Entrance>
    <ChallengeItem
      number="01"
      title="目标识别"
      detail="能否稳定辨认目标，而不只响应颜色？"
      top={344}
      delay={0.6}
    />
    <ChallengeItem
      number="02"
      title="停止时机"
      detail="何时继续走，何时才应该停？"
      top={497}
      delay={2.4}
    />
    <ChallengeItem
      number="03"
      title="新栈复测"
      detail="固定同一批起点，重新比较模型动作。"
      top={650}
      delay={4.2}
    />
    <Entrance
      delay={6}
      style={{
        position: "absolute",
        left: 100,
        top: 836,
        fontSize: 31,
        color: color.teal,
      }}
    >
      {facts.migration.testsPassed} 项本地测试通过 ≠ 导航效果提升。尚未完成 GPU
      闭环复测。
    </Entrance>
  </Scene>
);

export const DocumentarySample = () => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ background: color.paper }}>
      <Track name="纪录片场景">
        <Sequence
          name="开场 · 真实相机回放"
          from={0 * fps}
          durationInFrames={8 * fps}
        >
          <Opening />
        </Sequence>
        <Sequence
          name="闭环 · 示意动画"
          from={8 * fps}
          durationInFrames={10 * fps}
        >
          <ClosedLoop />
        </Sequence>
        <Sequence
          name="数据 · 轨迹与结构"
          from={18 * fps}
          durationInFrames={12 * fps}
        >
          <DataStructure />
        </Sequence>
        <Sequence
          name="训练 · 历史结果"
          from={30 * fps}
          durationInFrames={12 * fps}
        >
          <Training />
        </Sequence>
        <Sequence
          name="配对 · 同步动作步"
          from={42 * fps}
          durationInFrames={16 * fps}
        >
          <PairedReplay />
        </Sequence>
        <Sequence
          name="评测 · 全部十条"
          from={58 * fps}
          durationInFrames={10 * fps}
        >
          <Results />
        </Sequence>
        <Sequence
          name="挑战 · 待验证方向"
          from={68 * fps}
          durationInFrames={10 * fps}
        >
          <Challenge />
        </Sequence>
      </Track>
    </AbsoluteFill>
  );
};
