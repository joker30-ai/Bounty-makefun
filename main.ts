// Node 22-compatible offline entrypoint. The SVG is authored/rendered at build time.
const { chmodSync, mkdirSync, readFileSync, writeFileSync } = require("node:fs");
const { join } = require("node:path");

const image = readFileSync(join(__dirname, "assets", "entry.png"));
const signature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
if (image.length < 33 || image.length >= 1048576 ||
    !image.subarray(0, 8).equals(signature) || image.toString("ascii", 12, 16) !== "IHDR") {
  throw new Error("Expected a complete PNG smaller than 1 MiB.");
}
if (image.readUInt32BE(16) !== 1024 || image.readUInt32BE(20) !== 1024) {
  throw new Error("Expected the approved 1024 × 1024 editorial image.");
}

mkdirSync("/output", { recursive: true });
writeFileSync("/output/entry.png", image);
// The grader collects the image under a different user.
chmodSync("/output/entry.png", 0o644);
