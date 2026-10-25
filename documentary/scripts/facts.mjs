import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdirSync, readFileSync, realpathSync, statSync, writeFileSync} from 'node:fs';
import {dirname, isAbsolute, relative, resolve, sep} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const SOURCE_FILES = {
  evaluation: 'aima-open-session-experiment/experiments/exp02-equivalent-v3/eval_result.json',
  training: 'aima-open-session-experiment/experiments/exp02-equivalent-v3/stage2_result_v2.json',
  verification: 'security/evidence/model-migration-verification.json',
};
const IDS = Array.from({length: 10}, (_, i) => `eval-${2001 + i}`);
const ACTIONS = ['stop', 'forward', 'left', 'right'];
const SOURCE_LABELS = {
  data_replay: '真实数据回放',
  result_plot: '真实结果图',
  diagram: '示意动画',
  schema_visualization: '数据结构示意',
  metrics_visualization: '真实结果图',
};
const MEDIA_TYPES = new Set(['data_replay', 'result_plot']);
const same = (a, b, message) => assert.deepEqual(a, b, message);
const near = (a, b, message) => assert.ok(Number.isFinite(a) && Number.isFinite(b) && Math.abs(a - b) < 1e-8, message);
const sum = (rows, key) => rows.reduce((total, row) => total + Number(row[key]), 0);
const mean = (rows, key) => sum(rows, key) / rows.length;

function extractModel(evaluation, variant) {
  const model = evaluation[`${variant}_model`].model_evaluation;
  same(model.episode_ids, IDS, `${variant} held-out IDs differ`);
  same(model.same_heldout_batch, true, `${variant} held-out flag differs`);
  same(model.variant, variant, 'model variant differs');
  const summary = model.summary;
  const rows = summary.episodes_detail;
  same(rows.map((row) => row.episode_id), IDS, `${variant} held-out detail differs`);
  same(summary.episodes, IDS.length, 'held-out count differs');
  same(summary.success_0_5, 0, 'historical success changed; review the narrative');
  same(summary.success_0_5, sum(rows, 'success_0_5'), 'success aggregate differs');
  for (const [aggregate, key] of [
    ['collisions', 'collisions'], ['success_3', 'success_3'],
    ['oracle_success_0_5', 'oracle_success_0_5'], ['oracle_success_3', 'oracle_success_3'],
  ]) same(summary[aggregate], sum(rows, key), `${aggregate} aggregate differs`);
  for (const [aggregate, key] of [
    ['mean_final_distance_to_goal', 'final_distance_to_goal'],
    ['mean_min_distance_to_goal', 'min_distance_to_goal'], ['mean_path_length', 'path_length'],
    ['mean_spl_0_5', 'spl_0_5'], ['mean_steps', 'steps'],
  ]) near(summary[aggregate], mean(rows, key), `${aggregate} aggregate differs`);

  const episodes = rows.map((row) => {
    const observations = row.observations;
    same(observations.length, row.steps + 1, 'observation count differs');
    same(row.seed, Number(row.episode_id.slice(5)), 'held-out seed differs');
    near(row.shortest_path_length, observations[0].distance_to_goal_m, 'SPL proxy is not initial straight-line distance');
    const executed = row.predictions.flatMap((prediction) => prediction.actions).slice(0, row.steps);
    same(executed.length, row.steps, 'executed action count differs');
    assert.ok(executed.every((id) => Number.isInteger(id) && id >= 0 && id <= 3), 'invalid executed action');
    const counts = Object.fromEntries(ACTIONS.map((name, id) => [name, executed.filter((action) => action === id).length]));
    same(counts, row.action_counts, 'executed action statistics differ');
    same(observations.filter((o) => o.blocked).length, row.collisions, 'blocked/collision aggregate differs');
    for (const [index, observation] of observations.entries()) {
      same(observation.step_id, index, 'observation step differs');
      same(observation.collision, observation.blocked, 'collision is not safety-gate blocking');
      if (observation.blocked) {
        same(executed[index - 1], 1, 'blocked action is not forward');
        same(observation.blocked_source, 'head_depth_forward_guard', 'blocked source differs');
        same(observation.pose_matrix, observations[index - 1].pose_matrix, 'blocked action moved pose');
      }
    }
    const trajectory = observations.map((o, index) => ({
      step: o.step_id,
      xy: [o.pose_matrix[3], o.pose_matrix[7]],
      headingRad: Math.atan2(o.pose_matrix[4], o.pose_matrix[0]),
      distanceM: o.distance_to_goal_m,
      actionId: index === 0 ? null : executed[index - 1],
      blocked: o.blocked,
    }));
    return {
      id: row.episode_id, seed: row.seed, steps: row.steps,
      success: row.success_0_5, splProxy: row.spl_0_5,
      finalDistanceM: row.final_distance_to_goal, minDistanceM: row.min_distance_to_goal,
      pathLengthM: row.path_length, blockedForwardCount: row.collisions,
      actionCounts: counts, truncated: row.truncated,
      targetXY: [...observations[0].target_xy], trajectory,
    };
  });
  return {
    successCount: summary.success_0_5, auxiliarySuccess3m: summary.success_3,
    oracleSuccessCount: summary.oracle_success_0_5, splProxy: summary.mean_spl_0_5,
    meanFinalDistanceM: summary.mean_final_distance_to_goal,
    meanMinDistanceM: summary.mean_min_distance_to_goal,
    meanPathLengthM: summary.mean_path_length, meanSteps: summary.mean_steps,
    blockedForwardCount: summary.collisions,
    actionCounts: Object.fromEntries(ACTIONS.map((name) => [name, rows.reduce((total, row) => total + row.action_counts[name], 0)])),
    episodes,
  };
}

export function deriveFacts({evaluation, training, verification}) {
  same(evaluation.metric_source, 'eval_result.json', 'unexpected metric source');
  same(evaluation.heldout_episode_ids, IDS, 'held-out IDs differ');
  same(evaluation.same_heldout_batch, true, 'held-out pairing is unverified');
  const base = extractModel(evaluation, 'base');
  const lora = extractModel(evaluation, 'lora');
  base.episodes.forEach((episode, index) => {
    same(episode.trajectory[0], lora.episodes[index].trajectory[0], 'paired start differs');
    same(episode.targetXY, lora.episodes[index].targetXY, 'paired target differs');
  });
  const trainingGate = training.gates.full_training;
  same(trainingGate.status, 'passed', 'training did not pass');
  same(trainingGate.nan_or_inf, false, 'training nonfinite result');
  same(training.gates.dataset_only.valid, 50, 'training dataset count differs');
  same(verification.host.gpu_started, false, 'CPU-only boundary changed');
  same(verification.host.real_model_tensor_downloaded, false, 'CPU-only real-weight boundary changed');
  assert.ok(verification.tests.every((suite) => suite.failed === 0 && suite.exit_code === 0), 'migration tests failed');
  const facts = {
    schema_version: 'documentary-facts/v1',
    historical: {stack: 'historical', heldoutEpisodeIds: [...IDS], episodes: IDS.length, successRadiusM: 0.5, sameHeldoutBatch: true, base, lora},
    training: {
      stack: 'historical', episodes: training.gates.dataset_only.valid,
      updates: trainingGate.observed_steps, lossFirst: trainingGate.loss_first,
      lossLast: trainingGate.loss_last, lossSeriesAvailable: false,
      peakGpuMemoryMiB: trainingGate.peak_gpu_memory_mib,
      adapterReloadPassed: training.gates.adapter_reload.status === 'passed',
      lora: {rank: training.config.lora_r, alpha: training.config.lora_alpha,
        dropout: training.config.lora_dropout, epochs: training.config.epochs,
        batch: training.config.batch, learningRate: training.config.learning_rate},
    },
    migration: {date: verification.date, testsPassed: sum(verification.tests, 'passed'), gpuRetested: false, realWeightsLoaded: false, navigationCompared: false},
    metricSemantics: {
      collisions: {kind: 'blocked_forward_actions', label: '前进安全门拦截次数', physicalContactCount: false},
      spl: {kind: 'initial_straight_line_proxy', label: '初始直线距离代理 SPL', standardGeodesicSpl: false},
      historicalBoundary: '历史评测不代表新模型栈的导航效果',
    },
  };
  same(scanPublicText(facts), [], 'public facts contain sensitive text');
  return facts;
}

export function readCanonicalFacts(repoRoot) {
  const inputs = {};
  const provenance = {};
  for (const [key, relative] of Object.entries(SOURCE_FILES)) {
    const raw = readFileSync(resolve(repoRoot, relative));
    inputs[key] = JSON.parse(raw);
    provenance[key] = {sha256: createHash('sha256').update(raw).digest('hex')};
  }
  return {...deriveFacts(inputs), provenance};
}

export function scanPublicText(value) {
  const text = JSON.stringify(value);
  const checks = {
    private_path: /\/(?:Users|root|private|home)\//i,
    email: /[\w.+-]+@[\w.-]+\.[a-z]{2,}/i,
    address: /\b(?:\d{1,3}\.){3}\d{1,3}\b/,
    connection: /\b(?:ssh|password|access_token|api_key)\b/i,
    identity: /\bwode\b|组织名|实例编号|实例\s*ID/i,
    out_of_scope_claim: /课程|认证|证书|奖励|榜单成绩/,
  };
  return Object.entries(checks).filter(([, regex]) => regex.test(text)).map(([name]) => name);
}

function metricExists(facts, reference) {
  let value = facts;
  for (const part of reference.split('.')) {
    if (value === null || typeof value !== 'object' || !Object.hasOwn(value, part)) return false;
    value = value[part];
  }
  return true;
}

function safeMediaPath(path) {
  return typeof path === 'string' && /^[a-zA-Z0-9_./-]+$/.test(path)
    && !isAbsolute(path) && !path.split('/').includes('..') && !path.includes('://');
}

function segmentSources(segment) {
  const sources = [{role: 'source', source: segment.source, key: segment.id}];
  if (Object.hasOwn(segment, 'replaySource')) {
    sources.push({role: 'replaySource', source: segment.replaySource, key: `${segment.id}:replaySource`});
  }
  return sources;
}

function validateSource(source, key, sceneDuration) {
  if (!source || typeof source !== 'object' || Array.isArray(source)) return [`source schema:${key}`];
  const errors = [];
  if (!Object.hasOwn(SOURCE_LABELS, source.type) || SOURCE_LABELS[source.type] !== source.label) errors.push(`source label:${key}`);
  if (!Object.hasOwn(SOURCE_FILES, source.evidence)) errors.push(`source evidence:${key}`);
  if (typeof source.sourcePending !== 'boolean') errors.push(`source pending state:${key}`);
  if (source.mediaPath !== null && !safeMediaPath(source.mediaPath)) errors.push(`unsafe media path:${key}`);
  if (MEDIA_TYPES.has(source.type) && source.sourcePending === false && !source.mediaPath) errors.push(`false source readiness:${key}`);
  if (!MEDIA_TYPES.has(source.type) && source.mediaPath !== null) errors.push(`source classification:${key}`);
  if ((source.type === 'data_replay' && source.sourcePending === false) || source.timing != null) {
    const timing = source.timing;
    if (!timing || ![timing.startSec, timing.endSec, timing.sourceDurationSec, sceneDuration].every(Number.isFinite)
      || timing.startSec < 0 || timing.endSec <= timing.startSec || timing.sourceDurationSec <= 0
      || timing.endSec > timing.sourceDurationSec || timing.endSec - timing.startSec > sceneDuration) {
      errors.push(`source timing:${key}`);
    }
  }
  return errors;
}

function fileWithinPublicRoot(publicRoot, mediaPath) {
  if (!publicRoot || !safeMediaPath(mediaPath)) return false;
  try {
    const root = realpathSync(publicRoot);
    const file = realpathSync(resolve(publicRoot, mediaPath));
    const inside = relative(root, file);
    if (!inside || inside === '..' || inside.startsWith(`..${sep}`) || isAbsolute(inside)) return false;
    return statSync(file).isFile();
  } catch {
    // Missing roots/files, dangling links and inaccessible paths all fail closed.
    return false;
  }
}

export function validateStoryboard(sample, facts) {
  const errors = [];
  if (sample.schema_version !== 'documentary-storyboard/v1') errors.push('unsupported schema');
  if (sample.durationSec !== 78 || sample.fps !== 30) errors.push('sample duration or fps differs');
  if (!Array.isArray(sample.segments) || sample.segments.length !== 7) return [...errors, 'seven scenes required'];
  const ids = new Set();
  const lines = new Set();
  const sentences = new Set();
  let end = 0;
  for (const segment of sample.segments) {
    if (ids.has(segment.id)) errors.push(`duplicate ID:${segment.id}`);
    ids.add(segment.id);
    if (![segment.startSec, segment.endSec].every(Number.isFinite)
      || segment.startSec !== end || segment.endSec <= segment.startSec) errors.push(`timeline:${segment.id}`);
    end = segment.endSec;
    if (segment.loop !== false) errors.push(`loop forbidden:${segment.id}`);
    const narration = segment.narration.replace(/[\s\p{P}]/gu, '');
    if (!narration || lines.has(narration)) errors.push(`repeated narration:${segment.id}`);
    lines.add(narration);
    for (const sentence of segment.narration.split(/[。！？；]/u).map((part) => part.replace(/[\s\p{P}]/gu, '')).filter(Boolean)) {
      if (sentences.has(sentence)) errors.push(`repeated sentence:${segment.id}`);
      sentences.add(sentence);
    }
    const source = segment.source;
    for (const entry of segmentSources(segment)) {
      errors.push(...validateSource(entry.source, entry.key, segment.endSec - segment.startSec));
    }
    if (!Array.isArray(segment.metricRefs) || segment.metricRefs.some((reference) => !metricExists(facts, reference))) errors.push(`metric reference:${segment.id}`);
    if (segment.id === 'opening' && (source?.episodeId !== facts.historical.base.episodes[3].id
      || JSON.stringify(segment.metricRefs) !== JSON.stringify(['historical.base.episodes.3.id']))) errors.push('opening episode mapping differs');
    if (segment.id === 'paired-replay' && (source?.type !== 'metrics_visualization'
      || source.derivation !== 'canonical_pose_distance_actions' || source.mediaPath !== null
      || source.synchronization !== 'action_step'
      || source.note !== '真实轨迹记录重绘；按动作步同步，不代表墙钟时间'
      || segment.pairEpisodeId !== facts.historical.base.episodes[0].id
      || JSON.stringify(segment.metricRefs) !== JSON.stringify(['historical.base.episodes.0', 'historical.lora.episodes.0']))) errors.push('paired trace source differs');
    let cueEnd = 0;
    for (const cue of segment.subtitles ?? []) {
      if (cue.startSec < cueEnd || cue.endSec <= cue.startSec || cue.endSec > segment.endSec - segment.startSec) errors.push(`subtitle timing:${segment.id}`);
      cueEnd = cue.endSec;
      if (!cue.lines.length || cue.lines.length > 2 || cue.lines.some((line) => [...line].length > 16)) errors.push(`subtitle length:${segment.id}`);
    }
  }
  if (end !== sample.durationSec) errors.push('timeline end differs');
  const chineseCount = (sample.segments.map((s) => s.narration).join('').match(/\p{Script=Han}/gu) ?? []).length;
  if (chineseCount < 280 || chineseCount > 320) errors.push(`narration length:${chineseCount}`);
  return [...errors, ...scanPublicText(sample).map((kind) => `public text:${kind}`)];
}

export function publicationGate(sample, facts, {publicRoot} = {}) {
  const blockers = [...validateStoryboard(sample, facts)];
  if (sample.voice?.status !== 'approved' || !sample.voice.audioPath) blockers.push('voice_pending');
  if (sample.finalApproval !== true) blockers.push('final_approval_pending');
  for (const segment of sample.segments) {
    for (const {source, key} of segmentSources(segment)) {
      if (source?.sourcePending) blockers.push(`source_pending:${key}`);
      if (source?.mediaPath && !fileWithinPublicRoot(publicRoot, source.mediaPath)) blockers.push(`source_unverified:${key}`);
    }
  }
  if (sample.voice?.audioPath && !fileWithinPublicRoot(publicRoot, sample.voice.audioPath)) blockers.push('voice_file_unverified');
  return {ready: blockers.length === 0, blockers};
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
  const facts = readCanonicalFacts(repoRoot);
  const output = resolve(repoRoot, 'documentary/src/generated/facts.json');
  const rendered = `${JSON.stringify(facts, null, 2)}\n`;
  if (process.argv.includes('--check')) {
    assert.equal(readFileSync(output, 'utf8'), rendered, 'generated facts differ from canonical evidence');
  } else {
    mkdirSync(dirname(output), {recursive: true});
    writeFileSync(output, rendered);
  }
  console.log(`Documentary facts: ${facts.historical.episodes} paired episodes; ${facts.migration.testsPassed} CPU tests; GPU not retested.`);
}
