import assert from 'node:assert/strict';
import {existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import test from 'node:test';

const moduleUrl = new URL('../scripts/facts.mjs', import.meta.url);
const root = new URL('../../', import.meta.url);
const json = (relative) => JSON.parse(readFileSync(new URL(relative, root), 'utf8'));
const input = () => ({
  evaluation: json('aima-open-session-experiment/experiments/exp02-equivalent-v3/eval_result.json'),
  training: json('aima-open-session-experiment/experiments/exp02-equivalent-v3/stage2_result_v2.json'),
  verification: json('security/evidence/model-migration-verification.json'),
});

test('fact reader exists before the composition consumes metrics', async () => {
  assert.ok(existsSync(moduleUrl), 'Missing canonical fact reader');
  const api = await import(moduleUrl.href);
  assert.equal(typeof api.deriveFacts, 'function');
});

if (existsSync(moduleUrl)) {
  const {deriveFacts, validateStoryboard, publicationGate, scanPublicText, readCanonicalFacts} = await import(moduleUrl.href);
  const storyboard = () => json('documentary/content/sample.json');
  const fresh = () => deriveFacts(input());
  const readyFixture = (context) => {
    const directory = mkdtempSync(join(tmpdir(), 'documentary-gate-'));
    context.after(() => rmSync(directory, {recursive: true, force: true}));
    const publicRoot = join(directory, 'public');
    mkdirSync(join(publicRoot, 'media'), {recursive: true});
    for (const filename of ['base-2004.mp4', 'loss-curve.png', 'train-1001.mp4', 'voice.wav']) {
      writeFileSync(join(publicRoot, 'media', filename), 'Local file boundary test; decoding is verified separately.');
    }
    const sample = storyboard();
    sample.voice = {status: 'approved', audioPath: 'media/voice.wav', cloned: false};
    sample.finalApproval = true;
    const segment = sample.segments.find((s) => s.id === 'data-structure');
    segment.replaySource = {...segment.replaySource, type: 'data_replay', evidence: 'training', sourcePending: false};
    return {directory, publicRoot, sample, segment};
  };

  test('extracts both model results, never the controller validation success', () => {
    const facts = fresh();
    assert.equal(facts.historical.episodes, 10);
    assert.equal(facts.historical.successRadiusM, 0.5);
    for (const model of ['base', 'lora']) {
      assert.equal(facts.historical[model].successCount, 0);
      assert.equal(facts.historical[model].splProxy, 0);
    }
    assert.equal(facts.historical.base.blockedForwardCount, 132);
    assert.equal(facts.historical.lora.blockedForwardCount, 45);
    assert.equal(facts.historical.base.meanFinalDistanceM, 3.9889178097623224);
    assert.equal(facts.historical.lora.meanFinalDistanceM, 4.686244300975281);
  });

  test('rejects a different held-out batch or duplicate episode', () => {
    const data = input();
    data.evaluation.lora_model.model_evaluation.episode_ids[0] = 'eval-2099';
    assert.throws(() => deriveFacts(data), /held-out/);
    data.evaluation.lora_model.model_evaluation.episode_ids[0] = 'eval-2002';
    assert.throws(() => deriveFacts(data), /held-out/);
  });

  test('rejects changed aggregate metrics instead of silently editing the story', () => {
    const data = input();
    data.evaluation.base_model.model_evaluation.summary.success_0_5 = 1;
    assert.throws(() => deriveFacts(data), /success/);
  });

  test('collision count means blocked forward actions and requires matching evidence', () => {
    const facts = fresh();
    assert.equal(facts.metricSemantics.collisions.kind, 'blocked_forward_actions');
    assert.match(facts.metricSemantics.collisions.label, /安全门拦截/);
    const data = input();
    const row = data.evaluation.base_model.model_evaluation.summary.episodes_detail[0];
    row.observations.find((o) => o.blocked).blocked = false;
    assert.throws(() => deriveFacts(data), /blocked|collision/);
  });

  test('SPL explicitly remains an initial straight-line proxy', () => {
    const facts = fresh();
    assert.equal(facts.metricSemantics.spl.kind, 'initial_straight_line_proxy');
    assert.equal(facts.metricSemantics.spl.standardGeodesicSpl, false);
    const data = input();
    data.evaluation.base_model.model_evaluation.summary.episodes_detail[0].shortest_path_length = 99;
    assert.throws(() => deriveFacts(data), /SPL/);
  });

  test('paired replay is from the same starting pose and target', () => {
    const facts = fresh();
    const base = facts.historical.base.episodes[0];
    const lora = facts.historical.lora.episodes[0];
    assert.equal(base.id, lora.id);
    assert.deepEqual(base.trajectory[0].xy, lora.trajectory[0].xy);
    assert.deepEqual(base.targetXY, lora.targetXY);
    assert.equal(base.trajectory.length, base.steps + 1);
    assert.equal(lora.trajectory.length, lora.steps + 1);
    const data = input();
    data.evaluation.lora_model.model_evaluation.summary.episodes_detail[0].observations[0].pose_matrix[3] += 1;
    assert.throws(() => deriveFacts(data), /paired start/);
  });

  test('generated actions beyond a truncated episode are not counted as executed', () => {
    const facts = fresh();
    const episode = facts.historical.base.episodes.find((e) => e.id === 'eval-2007');
    assert.equal(episode.steps, 200);
    assert.equal(episode.trajectory.length, 201);
    assert.equal(Object.values(episode.actionCounts).reduce((a, b) => a + b, 0), 200);
  });

  test('training endpoints are not invented as a full loss curve', () => {
    const facts = fresh();
    assert.equal(facts.training.episodes, 50);
    assert.equal(facts.training.updates, 59);
    assert.equal(facts.training.lossFirst, 0.4167);
    assert.equal(facts.training.lossLast, 0.0823);
    assert.equal(facts.training.lossSeriesAvailable, false);
    assert.equal(facts.training.peakGpuMemoryMiB, 27846);
  });

  test('historical navigation and new CPU-only verification cannot be conflated', () => {
    const facts = fresh();
    assert.equal(facts.historical.stack, 'historical');
    assert.equal(facts.migration.gpuRetested, false);
    assert.equal(facts.migration.realWeightsLoaded, false);
    assert.equal(facts.migration.testsPassed, 132);
    const data = input();
    data.verification.host.gpu_started = true;
    assert.throws(() => deriveFacts(data), /CPU-only/);
  });

  test('allowlist extraction drops paths, connection details and upstream free text', () => {
    const data = input();
    data.evaluation.disclaimer = 'private forbidden input';
    data.training.command_file = '/private/should-never-be-exported';
    const facts = deriveFacts(data);
    assert.equal(JSON.stringify(facts).includes('private forbidden input'), false);
    assert.equal(JSON.stringify(facts).includes('should-never-be-exported'), false);
    assert.deepEqual(scanPublicText(facts), []);
  });

  test('source provenance contains hashes but no machine-specific source path', () => {
    const facts = readCanonicalFacts(fileURLToPath(root));
    assert.deepEqual(Object.keys(facts.provenance).sort(), ['evaluation', 'training', 'verification']);
    for (const record of Object.values(facts.provenance)) {
      assert.match(record.sha256, /^[a-f0-9]{64}$/);
      assert.equal('path' in record, false);
    }
  });

  test('sample has seven unique contiguous scenes totalling 78 seconds', () => {
    const sample = storyboard();
    assert.deepEqual(validateStoryboard(sample, fresh()), []);
    assert.equal(sample.segments.length, 7);
    assert.equal(sample.durationSec, 78);
    assert.deepEqual(sample.segments.map((s) => [s.startSec, s.endSec]), [[0,8],[8,18],[18,30],[30,42],[42,58],[58,68],[68,78]]);
  });

  test('opening binds the recovered eval-2004 clip and its own metric row', () => {
    const opening = storyboard().segments[0];
    assert.equal(opening.source.episodeId, 'eval-2004');
    assert.equal(opening.source.mediaPath, 'media/base-2004.mp4');
    assert.equal(opening.source.sourcePending, false);
    assert.deepEqual(opening.metricRefs, ['historical.base.episodes.3.id']);
    assert.deepEqual(opening.source.timing, {startSec: 0, endSec: 8, sourceDurationSec: 10});
    const wrong = storyboard();
    wrong.segments[0].metricRefs = ['historical.base.episodes.0.id'];
    assert.ok(validateStoryboard(wrong, fresh()).some((e) => /episode mapping/.test(e)));
  });

  test('paired scene redraws eval-2001 logs and does not masquerade as raw RGB', () => {
    const paired = storyboard().segments.find((s) => s.id === 'paired-replay');
    assert.equal(paired.pairEpisodeId, 'eval-2001');
    assert.equal(paired.source.type, 'metrics_visualization');
    assert.equal(paired.source.label, '真实结果图');
    assert.equal(paired.source.mediaPath, null);
    assert.equal(paired.source.sourcePending, false);
    assert.equal(paired.source.synchronization, 'action_step');
    assert.equal(paired.source.note, '真实轨迹记录重绘；按动作步同步，不代表墙钟时间');
    assert.deepEqual(paired.metricRefs, ['historical.base.episodes.0', 'historical.lora.episodes.0']);
    const wrong = storyboard();
    wrong.segments.find((s) => s.id === 'paired-replay').source.type = 'data_replay';
    assert.ok(validateStoryboard(wrong, fresh()).some((e) => /paired trace source/.test(e)));
  });

  test('training uses the recovered actual curve, not a fabricated endpoint interpolation', () => {
    const training = storyboard().segments.find((s) => s.id === 'training');
    assert.equal(training.source.mediaPath, 'media/loss-curve.png');
    assert.equal(training.source.sourcePending, false);
    assert.equal(training.source.derivation, 'historical_training_curve_screenshot');
    assert.equal(fresh().training.lossSeriesAvailable, false);
  });

  test('rejects gaps, duplicate scene IDs, missing metric references and narration reuse', () => {
    for (const change of [
      (s) => {s.segments[1].startSec = 9;},
      (s) => {s.segments[1].id = s.segments[0].id;},
      (s) => {s.segments[3].metricRefs = ['training.inventedMetric'];},
      (s) => {s.segments[1].narration = s.segments[0].narration;},
      (s) => {s.segments[0].loop = true;},
    ]) {
      const sample = storyboard();
      change(sample);
      assert.ok(validateStoryboard(sample, fresh()).length > 0);
    }
  });

  test('source label cannot call data replay a continuous desktop recording', () => {
    const sample = storyboard();
    sample.segments[0].source.label = '操作录屏';
    assert.ok(validateStoryboard(sample, fresh()).some((e) => /source label/.test(e)));
  });

  test('rejects repeated full sentences inside otherwise different narration', () => {
    const sample = storyboard();
    sample.segments[1].narration += `。${sample.segments[0].narration.split('。')[0]}。`;
    assert.ok(validateStoryboard(sample, fresh()).some((e) => /repeated sentence/.test(e)));
  });

  test('narration document contains every spoken sentence from the storyboard', () => {
    const document = readFileSync(new URL('documentary/content/narration.md', root), 'utf8');
    for (const segment of storyboard().segments) assert.ok(document.includes(segment.narration));
  });

  test('narration is 280–320 Chinese characters and subtitle lines stay short', () => {
    const sample = storyboard();
    const count = (sample.segments.map((s) => s.narration).join('').match(/\p{Script=Han}/gu) ?? []).length;
    assert.ok(count >= 280 && count <= 320, `Chinese narration count: ${count}`);
    for (const segment of sample.segments) {
      for (const cue of segment.subtitles) {
        assert.ok(cue.lines.length <= 2);
        for (const line of cue.lines) assert.ok([...line].length <= 16);
      }
    }
  });

  test('privacy gate rejects contacts, addresses, course and unsupported reward claims', () => {
    for (const text of ['课程复现', '认证奖励', 'hello@example.com', '192.168.0.1', '/Users/person/file', 'ssh host', 'wode组织']) {
      assert.ok(scanPublicText({text}).length > 0, text);
    }
    assert.deepEqual(scanPublicText(storyboard()), []);
  });

  test('missing voice and final approval block publication but permit visual preview', () => {
    const sample = storyboard();
    assert.equal(sample.status, 'visual_preview_pending_voice');
    assert.deepEqual(validateStoryboard(sample, fresh()), []);
    const gate = publicationGate(sample, fresh());
    assert.equal(gate.ready, false);
    assert.ok(gate.blockers.includes('voice_pending'));
    assert.equal(gate.blockers.some((b) => b.startsWith('source_pending:')), false);
    assert.ok(gate.blockers.includes('final_approval_pending'));
  });

  test('an unresolved footage fixture still fails the source publication gate', () => {
    const sample = storyboard();
    sample.segments[0].source.sourcePending = true;
    sample.segments[0].source.mediaPath = null;
    sample.segments[0].source.timing = null;
    const gate = publicationGate(sample, fresh());
    assert.equal(gate.ready, false);
    assert.ok(gate.blockers.includes('source_pending:opening'));
  });

  test('media bindings reject traversal, absolute paths and false readiness', () => {
    for (const path of ['../secret.mp4', '/tmp/video.mp4', 'https://example.com/video.mp4']) {
      const sample = storyboard();
      sample.segments[0].source.mediaPath = path;
      assert.ok(validateStoryboard(sample, fresh()).length > 0);
    }
    const sample = storyboard();
    sample.segments[0].source.sourcePending = false;
    sample.segments[0].source.mediaPath = null;
    assert.ok(validateStoryboard(sample, fresh()).length > 0);
  });

  test('auxiliary replay declares a complete source classification and pending state', () => {
    const source = storyboard().segments.find((s) => s.id === 'data-structure').replaySource;
    assert.equal(source.type, 'data_replay');
    assert.equal(source.evidence, 'training');
    assert.equal(source.sourcePending, false);
  });

  test('legal replay files permit the file-boundary gate after explicit voice and final approval', (context) => {
    const {sample, publicRoot} = readyFixture(context);
    assert.deepEqual(validateStoryboard(sample, fresh()), []);
    assert.deepEqual(publicationGate(sample, fresh(), {publicRoot}), {ready: true, blockers: []});
  });

  test('both primary and auxiliary source paths reject traversal even if the outside file exists', (context) => {
    const fixture = readyFixture(context);
    writeFileSync(join(fixture.directory, 'not-in-public-root.mp4'), 'outside');
    for (const slot of ['source', 'replaySource']) {
      const sample = structuredClone(fixture.sample);
      const source = slot === 'source' ? sample.segments[0].source : sample.segments[2].replaySource;
      source.mediaPath = '../not-in-public-root.mp4';
      assert.ok(validateStoryboard(sample, fresh()).some((error) => /unsafe media path/.test(error)), slot);
      assert.equal(publicationGate(sample, fresh(), {publicRoot: fixture.publicRoot}).ready, false, slot);
    }
  });

  test('auxiliary missing files, dangling symlinks and directory paths block publication', (context) => {
    const {sample, publicRoot, segment} = readyFixture(context);
    const paths = ['media/missing.mp4', 'media/dangling.mp4', 'media'];
    symlinkSync(join(publicRoot, 'media', 'absent-target.mp4'), join(publicRoot, 'media', 'dangling.mp4'));
    for (const path of paths) {
      segment.replaySource.mediaPath = path;
      const result = publicationGate(sample, fresh(), {publicRoot});
      assert.equal(result.ready, false, path);
      assert.ok(result.blockers.some((error) => error.includes('source_unverified:data-structure:replaySource')), path);
    }
  });

  test('realpath containment rejects primary, replay and voice symlinks outside the public root', (context) => {
    const fixture = readyFixture(context);
    const sibling = join(fixture.directory, 'public-sibling');
    mkdirSync(sibling);
    const outside = join(sibling, 'outside.mp4');
    writeFileSync(outside, 'outside');
    symlinkSync(outside, join(fixture.publicRoot, 'media', 'escaped.mp4'));
    for (const slot of ['source', 'replaySource', 'voice']) {
      const sample = structuredClone(fixture.sample);
      if (slot === 'source') sample.segments[0].source.mediaPath = 'media/escaped.mp4';
      if (slot === 'replaySource') sample.segments[2].replaySource.mediaPath = 'media/escaped.mp4';
      if (slot === 'voice') sample.voice.audioPath = 'media/escaped.mp4';
      assert.equal(publicationGate(sample, fresh(), {publicRoot: fixture.publicRoot}).ready, false, slot);
    }
  });

  test('an in-root replay symlink is valid and a pending replay is not publishable', (context) => {
    const {sample, publicRoot, segment} = readyFixture(context);
    symlinkSync(join(publicRoot, 'media', 'train-1001.mp4'), join(publicRoot, 'media', 'alias.mp4'));
    segment.replaySource.mediaPath = 'media/alias.mp4';
    assert.equal(publicationGate(sample, fresh(), {publicRoot}).ready, true);
    segment.replaySource.sourcePending = true;
    segment.replaySource.mediaPath = null;
    segment.replaySource.timing = null;
    const result = publicationGate(sample, fresh(), {publicRoot});
    assert.equal(result.ready, false);
    assert.ok(result.blockers.includes('source_pending:data-structure:replaySource'));
  });

  test('source classification and explicit pending booleans are checked for both source roles', () => {
    for (const [slot, index] of [['source', 0], ['replaySource', 2]]) {
      for (const change of [
        (source) => {source.type = 'invented';},
        (source) => {source.label = '操作录屏';},
        (source) => {source.evidence = 'unverified';},
        (source) => {delete source.sourcePending;},
        (source) => {source.sourcePending = 'false';},
      ]) {
        const sample = storyboard();
        change(sample.segments[index][slot]);
        assert.ok(validateStoryboard(sample, fresh()).length > 0, slot);
      }
    }
  });

  test('all video timing is finite, positive in length, within source and scene bounds', () => {
    const invalidTimings = [
      null,
      {startSec: -1, endSec: 8, sourceDurationSec: 10},
      {startSec: 0, endSec: 0, sourceDurationSec: 10},
      {startSec: 0, endSec: NaN, sourceDurationSec: 10},
      {startSec: 0, endSec: 8, sourceDurationSec: Infinity},
      {startSec: 0, endSec: 8, sourceDurationSec: -10},
      {startSec: 0, endSec: 11, sourceDurationSec: 10},
      {startSec: 0, endSec: 13, sourceDurationSec: 20},
    ];
    for (const [slot, index] of [['source', 0], ['replaySource', 2]]) {
      for (const timing of invalidTimings) {
        const sample = storyboard();
        sample.segments[index][slot].timing = timing;
        assert.ok(validateStoryboard(sample, fresh()).some((error) => /source timing/.test(error)), `${slot}: ${JSON.stringify(timing)}`);
      }
    }
  });
}
