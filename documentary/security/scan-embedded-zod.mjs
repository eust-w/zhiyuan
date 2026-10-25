import {createHash} from 'node:crypto';
import {readdirSync, readFileSync, writeFileSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const findings = [];
const visit = (directory) => {
  for (const entry of readdirSync(directory, {withFileTypes: true})) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) visit(file);
    else if (entry.isFile() && /\.(?:c|m)?js$/.test(entry.name)) {
      const content = readFileSync(file);
      const text = content.toString('utf8');
      if (/zod@4\.5\.4/.test(text) || (/major: 4,\s+minor: 5,\s+patch: 4/.test(text) && text.includes('$ZodArray'))) {
        findings.push({file: path.relative(root, file), sha256: createHash('sha256').update(content).digest('hex'),
          embeddedVersion: '4.5.4', status: 'unpatched_bundled_dependency',
          note: 'npm overrides do not rewrite pre-bundled code; upstream size-gate fix absent',
        });
      }
    }
  }
};
visit(path.join(root, 'node_modules/@remotion'));
findings.sort((a, b) => a.file.localeCompare(b.file));
const report = {scannedAt: new Date().toISOString(), scope: '@remotion installed JavaScript files',
  completeSecurityRemediation: false, findings};
writeFileSync(new URL('embedded-zod.json', import.meta.url), `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify({unpatchedEmbeddedFiles: findings.length, completeSecurityRemediation: false}));
