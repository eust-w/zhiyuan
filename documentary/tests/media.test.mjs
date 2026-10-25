import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {existsSync, mkdtempSync, writeFileSync, rmSync, symlinkSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import test from 'node:test';

const moduleUrl = new URL('../scripts/media.mjs', import.meta.url);
test('media integrity reader exists before public previews consume files', () => {
  assert.ok(existsSync(moduleUrl), 'Missing media integrity reader');
});

if (existsSync(moduleUrl)) {
  const {verifyFile, assertSafeRelative, verifyProbe, assertCoverage, assertWriteTarget} = await import(moduleUrl.href);
  test('rejects unsafe asset paths', () => {
    for (const path of ['../x', '/tmp/x', 'https://example.invalid/x', 'media/../../x', 'media\\x']) {
      assert.throws(() => assertSafeRelative(path));
    }
    assertSafeRelative('media/base-2004.mp4');
  });
  test('actual bytes must match hash and symlinks cannot escape the root', () => {
    const root = mkdtempSync(join(tmpdir(), 'documentary-media-'));
    try {
      const bytes = Buffer.from('original test asset');
      writeFileSync(join(root, 'asset'), bytes);
      const item = {path: 'asset', sha256: createHash('sha256').update(bytes).digest('hex')};
      assert.equal(verifyFile(root, item).sha256, item.sha256);
      writeFileSync(join(root, 'asset'), 'changed');
      assert.throws(() => verifyFile(root, item), /hash mismatch/);
      symlinkSync('/etc/hosts', join(root, 'escape'));
      assert.throws(() => verifyFile(root, {...item, path: 'escape'}), /outside media root/);
    } finally { rmSync(root, {recursive: true, force: true}); }
  });
  test('video must be long enough, H.264, 1080p30 and silent', () => {
    const item = {kind: 'video', requiredDurationSec: 8};
    const probe = {format: {duration: '10'}, streams: [{codec_type: 'video', codec_name: 'h264', width: 1920, height: 1080, r_frame_rate: '30/1'}]};
    assert.doesNotThrow(() => verifyProbe(item, probe));
    assert.throws(() => verifyProbe(item, {...probe, format: {duration: '7'}}), /duration/);
    assert.throws(() => verifyProbe(item, {...probe, streams: [...probe.streams, {codec_type: 'audio'}]}), /silent/);
    assert.throws(() => verifyProbe(item, {...probe, streams: [{...probe.streams[0], width: 960}]}), /resolution/);
  });
  test('preparation refuses dangling and existing symlinks before writing', () => {
    const root = mkdtempSync(join(tmpdir(), 'documentary-write-'));
    try {
      symlinkSync(join(root, 'missing-target'), join(root, 'dangling'));
      writeFileSync(join(root, 'ordinary'), 'safe');
      symlinkSync(join(root, 'ordinary'), join(root, 'internal-link'));
      assert.equal(typeof assertWriteTarget, 'function');
      assert.throws(() => assertWriteTarget(root, 'dangling'), /symlink/);
      assert.throws(() => assertWriteTarget(root, 'internal-link'), /symlink/);
      assert.doesNotThrow(() => assertWriteTarget(root, 'ordinary'));
      assert.doesNotThrow(() => assertWriteTarget(root, 'new-file'));
    } finally { rmSync(root, {recursive: true, force: true}); }
  });
  test('every authored media reference must exist in the provenance manifest', () => {
    const sample = {segments: [{source: {mediaPath: 'media/a.mp4'}, replaySource: {mediaPath: 'media/b.mp4'}}]};
    assert.throws(() => assertCoverage(sample, {assets: [{path: 'media/a.mp4'}]}), /untracked media/);
    assert.doesNotThrow(() => assertCoverage(sample, {assets: [{path: 'media/a.mp4'}, {path: 'media/b.mp4'}]}));
  });
}
