import assert from 'node:assert/strict';
import {once} from 'node:events';
import {createServer} from 'node:net';
import {createRequire} from 'node:module';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import test from 'node:test';

const require = createRequire(import.meta.url);
const {enforceLoopback} = require('./loopback-studio.cjs');

test('both Remotion address modes are pinned to loopback', () => {
  enforceLoopback();
  const {RenderInternals} = require('@remotion/renderer');
  for (const preferIpv4 of [true, false]) {
    assert.deepEqual(RenderInternals.getPortConfig(preferIpv4), {
      host: '127.0.0.1', hostsToTry: ['127.0.0.1'],
    });
  }
});

test('the enforced config opens a real loopback socket, not a wildcard listener', async () => {
  const config = enforceLoopback();
  const server = createServer();
  try {
    server.listen({host: config.host, port: 0});
    await once(server, 'listening');
    assert.equal(server.address().address, '127.0.0.1');
  } finally {
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
});

test('the launcher reaches the installed Remotion Studio CLI', () => {
  const result = spawnSync(process.execPath, [fileURLToPath(new URL('./loopback-studio.cjs', import.meta.url)), '--help'], {
    encoding: 'utf8', timeout: 20000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /remotion studio/);
});
