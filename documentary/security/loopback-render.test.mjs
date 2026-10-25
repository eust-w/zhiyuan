import assert from 'node:assert/strict';
import {existsSync} from 'node:fs';
import {createRequire} from 'node:module';
import test from 'node:test';

const entry = new URL('./loopback-render.cjs', import.meta.url);
test('rendering uses a dedicated loopback-protected CLI', () => {
  assert.ok(existsSync(entry), 'missing protected render launcher');
});
if (existsSync(entry)) {
  const require = createRequire(import.meta.url);
  const {validateOperation} = require('./loopback-render.cjs');
  test('only known local rendering commands are permitted', () => {
    for (const operation of ['render', 'still', 'compositions']) assert.doesNotThrow(() => validateOperation(operation));
    for (const operation of [undefined, 'studio', 'lambda', 'upgrade', '--help']) assert.throws(() => validateOperation(operation));
  });
}
