import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {constants, lstatSync, mkdirSync, readFileSync, realpathSync, writeFileSync} from 'node:fs';
import {dirname, isAbsolute, relative, resolve} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const digest = (bytes) => createHash('sha256').update(bytes).digest('hex');
export function assertSafeRelative(path) {
  assert.ok(typeof path === 'string' && /^[a-zA-Z0-9_./-]+$/.test(path)
    && !isAbsolute(path) && !path.split('/').includes('..') && !path.startsWith('-'), 'unsafe media path');
}
function inside(root, target) {
  const path = relative(realpathSync(root), realpathSync(target));
  assert.ok(!path.startsWith('..') && !isAbsolute(path), 'outside media root');
}
export function verifyFile(publicRoot, asset) {
  assertSafeRelative(asset.path);
  const target = resolve(publicRoot, asset.path);
  inside(publicRoot, target);
  const bytes = readFileSync(target);
  const sha256 = digest(bytes);
  assert.equal(sha256, asset.sha256, `hash mismatch: ${asset.path}`);
  return {path: asset.path, sha256, bytes: bytes.length};
}
export function assertWriteTarget(publicRoot, path) {
  assertSafeRelative(path);
  const target = resolve(publicRoot, path);
  inside(publicRoot, dirname(target));
  try {
    const stat = lstatSync(target);
    assert.ok(!stat.isSymbolicLink(), 'refusing symlink media destination');
    assert.ok(stat.isFile(), 'media destination is not a regular file');
    inside(publicRoot, target);
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
  return target;
}
export function verifyProbe(asset, probe) {
  const video = probe.streams.find((s) => s.codec_type === 'video');
  assert.ok(video, 'missing video/image stream');
  if (asset.kind === 'video') {
    assert.equal(video.codec_name, 'h264', 'video codec differs');
    assert.equal(video.width, 1920, 'resolution width differs');
    assert.equal(video.height, 1080, 'resolution height differs');
    assert.equal(video.r_frame_rate, '30/1', 'frame rate differs');
    assert.ok(Number(probe.format.duration) >= asset.requiredDurationSec, 'insufficient source duration');
    assert.ok(!probe.streams.some((s) => s.codec_type === 'audio'), 'historical replay must be silent');
  }
}
export function assertCoverage(sample, manifest) {
  const paths = new Set(manifest.assets.map((asset) => asset.path));
  for (const segment of sample.segments) {
    for (const source of [segment.source, segment.replaySource]) {
      if (source?.mediaPath) assert.ok(paths.has(source.mediaPath), `untracked media: ${source.mediaPath}`);
    }
  }
}
export function prepareMedia(repoRoot, publicRoot, manifest) {
  assert.match(manifest.sourceCommit, /^[a-f0-9]{40}$/);
  for (const asset of manifest.assets) {
    assertSafeRelative(asset.path);
    assertSafeRelative(asset.sourcePath);
    // Materialize only three explicitly hashed Git objects, never the full archive.
    const bytes = execFileSync('git', ['show', `${manifest.sourceCommit}:${asset.sourcePath}`],
      {cwd: repoRoot, maxBuffer: 20 * 1024 * 1024, timeout: 120000});
    assert.equal(digest(bytes), asset.sha256, `source hash mismatch: ${asset.path}`);
    const target = resolve(publicRoot, asset.path);
    mkdirSync(dirname(target), {recursive: true});
    assertWriteTarget(publicRoot, asset.path);
    // O_NOFOLLOW also rejects a leaf symlink inserted after the lstat check.
    writeFileSync(target, bytes, {flag: constants.O_WRONLY | constants.O_CREAT | constants.O_TRUNC | constants.O_NOFOLLOW});
  }
}
export function verifyMedia(publicRoot, manifest, {decode = false} = {}) {
  return manifest.assets.map((asset) => {
    const file = verifyFile(publicRoot, asset);
    const target = resolve(publicRoot, asset.path);
    const probe = JSON.parse(execFileSync('ffprobe', ['-v', 'error', '-show_format', '-show_streams', '-of', 'json', target], {timeout: 30000}));
    verifyProbe(asset, probe);
    if (decode) execFileSync('ffmpeg', ['-v', 'error', '-xerror', '-i', target, '-f', 'null', '-'], {timeout: 120000});
    const stream = probe.streams.find((s) => s.codec_type === 'video');
    return {...file, codec: stream.codec_name, width: stream.width, height: stream.height,
      durationSec: probe.format.duration ? Number(probe.format.duration) : null, fullDecodePassed: decode};
  });
}
if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const project = resolve(dirname(fileURLToPath(import.meta.url)), '..');
  const manifest = JSON.parse(readFileSync(resolve(project, 'content/media.json')));
  const sample = JSON.parse(readFileSync(resolve(project, 'content/sample.json')));
  const publicRoot = resolve(project, 'public');
  assertCoverage(sample, manifest);
  if (process.argv.includes('--prepare')) prepareMedia(resolve(project, '..'), publicRoot, manifest);
  const assets = verifyMedia(publicRoot, manifest, {decode: process.argv.includes('--decode')});
  mkdirSync(resolve(project, 'out'), {recursive: true});
  writeFileSync(resolve(project, 'out/media-verification.json'), `${JSON.stringify({schema_version: 'documentary-media-verification/v1', assets}, null, 2)}\n`);
  console.log(`Verified ${assets.length} exact-source assets${process.argv.includes('--decode') ? ', all fully decoded' : ''}. No continuous desktop-recording claim.`);
}
