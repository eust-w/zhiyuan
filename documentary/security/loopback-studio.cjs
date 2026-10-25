"use strict";

// Remotion 4.0.538 has no host flag: --ipv4 still binds 0.0.0.0.
// This process-local adapter changes no dependency files and fails on upgrades.
const assert = require("node:assert/strict");
const path = require("node:path");

const enforceLoopback = () => {
  const version = require("remotion/package.json").version;
  assert.equal(version, "4.0.538", "Review the loopback adapter before upgrading Remotion");
  const {RenderInternals} = require("@remotion/renderer");
  assert.equal(typeof RenderInternals.getPortConfig, "function");
  const config = Object.freeze({host: "127.0.0.1", hostsToTry: Object.freeze(["127.0.0.1"])});
  RenderInternals.getPortConfig = () => config;
  assert.strictEqual(RenderInternals.getPortConfig(false), config);
  assert.strictEqual(RenderInternals.getPortConfig(true), config);
  return config;
};

module.exports = {enforceLoopback};

if (require.main === module) {
  try {
    process.chdir(path.resolve(__dirname, ".."));
    enforceLoopback();
    process.argv.splice(2, 0, "studio");
    require("@remotion/cli").cli().catch((error) => {
      console.error("Loopback Studio failed:", error.message);
      process.exit(1);
    });
  } catch (error) {
    console.error("Loopback Studio refused to start:", error.message);
    process.exit(1);
  }
}
