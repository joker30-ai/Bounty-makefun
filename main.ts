// Node 22-compatible; built-in modules only. No network, clocks, or randomness.
const { chmodSync, copyFileSync, mkdirSync } = require("node:fs");
const { join } = require("node:path");

mkdirSync("/output", { recursive: true });
copyFileSync(join(__dirname, "assets", "entry.png"), "/output/entry.png");
// The grader collects the image under a different user.
chmodSync("/output/entry.png", 0o644);
