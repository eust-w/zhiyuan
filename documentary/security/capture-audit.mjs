import {createHash} from 'node:crypto';
import {readFileSync, writeFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const phase = process.argv[2];
if (!['before', 'after'].includes(phase)) throw new Error('Usage: node security/capture-audit.mjs before|after');
const root = fileURLToPath(new URL('../', import.meta.url));
const result = spawnSync('npm', ['audit', '--json'], {cwd: root, encoding: 'utf8', timeout: 120000});
if (result.error) throw result.error;
const report = JSON.parse(result.stdout);
if (!report.metadata || report.error) throw new Error('npm audit did not return a complete advisory report');
const evidence = {
  capturedAt: new Date().toISOString(),
  command: 'npm audit --json',
  exitCode: result.status,
  nodeVersion: process.version,
  lockfileSha256: createHash('sha256').update(readFileSync(new URL('../package-lock.json', import.meta.url))).digest('hex'),
  report,
};
writeFileSync(new URL(`npm-audit.${phase}.json`, import.meta.url), `${JSON.stringify(evidence, null, 2)}\n`);
console.log(JSON.stringify({phase, exitCode: result.status, vulnerabilities: report.metadata.vulnerabilities}));
