"use strict";
const assert = require("node:assert/strict");
const path = require("node:path");
const {enforceLoopback} = require("./loopback-studio.cjs");

function validateOperation(operation) {
  assert.ok(["render", "still", "compositions"].includes(operation), "Only local render, still and compositions commands are supported");
}
module.exports = {validateOperation};

if (require.main === module) {
  try {
    validateOperation(process.argv[2]);
    process.chdir(path.resolve(__dirname, ".."));
    enforceLoopback();
    require("@remotion/cli").cli().catch((error) => {
      console.error("Local rendering failed:", error.message);
      process.exitCode = 1;
    });
  } catch (error) {
    console.error("Local rendering refused:", error.message);
    process.exitCode = 1;
  }
}
