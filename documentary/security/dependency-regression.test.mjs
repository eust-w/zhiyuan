import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import test from 'node:test';

const require = createRequire(import.meta.url);

test('the resolved Zod dependency is the advisory-patched version', () => {
  assert.equal(require('zod/package.json').version, '4.6.6');
});

test('Remotion packages remain on the same pinned release', () => {
  const lock = JSON.parse(readFileSync(new URL('../package-lock.json', import.meta.url)));
  for (const [name, entry] of Object.entries(lock.packages)) {
    if (/node_modules\/(?:@remotion\/[^/]+|remotion)$/.test(name)) {
      assert.equal(entry.version, '4.0.538', name);
    }
  }
});

test('Remotion-used Zod Mini and legacy v3 entry points still parse basic payloads', () => {
  const mini = require('zod/mini');
  const legacy = require('zod/v3');
  assert.deepEqual(mini.object({name: mini.string()}).parse({name: 'preview'}), {name: 'preview'});
  assert.deepEqual(legacy.object({frames: legacy.number()}).parse({frames: 30}), {frames: 30});
});

test('the patched bounded-array parser rejects excess size before visiting elements', () => {
  const z = require('zod');
  let visits = 0;
  const schema = z.array(z.custom(() => { visits += 1; return false; })).max(1);
  const result = schema.safeParse([1, 2, 3]);
  assert.equal(result.success, false);
  assert.equal(visits, 0);
  assert.equal(result.error.issues.length, 1);
  assert.equal(result.error.issues[0].code, 'too_big');
});
