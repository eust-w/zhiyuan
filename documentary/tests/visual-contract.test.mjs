import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const root = new URL("../", import.meta.url);
const facts = JSON.parse(
  await readFile(new URL("src/generated/facts.json", root)),
);
const storyboard = JSON.parse(
  await readFile(new URL("content/sample.json", root)),
);
const moduleSource = await readFile(
  new URL("src/visual-model.ts", root),
  "utf8",
);
const compiled = ts.transpileModule(moduleSource, {
  compilerOptions: {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.ES2022,
  },
});
const model = await import(
  `data:text/javascript;base64,${Buffer.from(compiled.outputText).toString("base64")}`
);

test("the same held-out episode shares a step clock and stops at its own final state", () => {
  const base = facts.historical.base.episodes[0];
  const lora = facts.historical.lora.episodes[0];
  assert.equal(base.id, lora.id);
  const endStep = Math.max(base.steps, lora.steps);
  assert.deepEqual(model.stateAtStep(base.trajectory, 0), base.trajectory[0]);
  assert.deepEqual(
    model.stateAtStep(lora.trajectory, endStep),
    lora.trajectory.at(-1),
  );
  assert.equal(model.stepForFrame(0, 30, 16, endStep), 0);
  assert.equal(model.stepForFrame(16 * 30 - 1, 30, 16, endStep), endStep);
  assert.throws(() => model.stateAtStep([], 0), /empty/);
});

test("both trajectory panels use one equal-axis projection including the target", () => {
  const pair = [
    facts.historical.base.episodes[0],
    facts.historical.lora.episodes[0],
  ];
  const projection = model.pairedProjection(pair, 740, 460, 46);
  const origin = projection.point([0, 0]);
  const x = projection.point([1, 0]);
  const y = projection.point([0, 1]);
  assert.ok(
    Math.abs(Math.abs(x[0] - origin[0]) - Math.abs(y[1] - origin[1])) < 1e-9,
  );
  for (const episode of pair) {
    for (const xy of [
      episode.targetXY,
      ...episode.trajectory.map((s) => s.xy),
    ]) {
      const point = projection.point(xy);
      assert.ok(point[0] >= 46 && point[0] <= 694);
      assert.ok(point[1] >= 46 && point[1] <= 414);
    }
  }
  assert.ok(projection.radius(facts.historical.successRadiusM) > 0);
});

test("the documentary has explicit editable scene nodes matching its approved timing", async () => {
  const composition = await readFile(
    new URL("src/Composition.tsx", root),
    "utf8",
  );
  const registration = await readFile(new URL("src/Root.tsx", root), "utf8");
  for (const name of [
    "开场 · 真实相机回放",
    "闭环 · 示意动画",
    "数据 · 轨迹与结构",
    "训练 · 历史结果",
    "配对 · 同步动作步",
    "评测 · 全部十条",
    "挑战 · 待验证方向",
  ]) {
    assert.ok(
      composition.includes(`name="${name}"`),
      `missing editable scene: ${name}`,
    );
  }
  const authoredSceneTimes = [
    ...composition.matchAll(
      /name="(?:开场 · 真实相机回放|闭环 · 示意动画|数据 · 轨迹与结构|训练 · 历史结果|配对 · 同步动作步|评测 · 全部十条|挑战 · 待验证方向)"\s+from=\{(\d+) \* fps\}\s+durationInFrames=\{(\d+) \* fps\}/g,
    ),
  ];
  assert.deepEqual(
    authoredSceneTimes.map((match) => [Number(match[1]), Number(match[2])]),
    storyboard.segments.map((item) => [
      item.startSec,
      item.endSec - item.startSec,
    ]),
  );
  assert.match(registration, /id="DocumentarySample"/);
  assert.match(registration, /durationInFrames=\{2340\}/);
  assert.match(registration, /fps=\{30\}/);
  assert.match(registration, /width=\{1920\}/);
  assert.match(registration, /height=\{1080\}/);
  assert.equal(storyboard.durationSec * storyboard.fps, 2340);
  assert.doesNotMatch(
    composition,
    /loop=\{true\}|<Loop\b|animation:|transition:/,
  );
  assert.match(composition, /视觉样片 · 配音待确认/);
  assert.match(composition, /真实轨迹重绘/);
  assert.match(composition, /不是实体接触碰撞/);
  assert.match(composition, /尚未完成 GPU\s+闭环复测/);
});
