const fs = require("node:fs");
const path = require("node:path");

const srcDir = path.resolve(__dirname, "..", "src");
const targetExtensions = new Set([".css", ".ts", ".tsx"]);
const patterns = [
  /\uFFFD/,
  /\?{1,3}\uC1F1\uC819/,
  /\u936E/,
  /\?\uC497\uAE6E/,
  /\?\uBEA4\uC524/,
];

function findSourceFiles(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...findSourceFiles(fullPath));
      continue;
    }

    if (entry.isFile() && targetExtensions.has(path.extname(entry.name))) {
      files.push(fullPath);
    }
  }

  return files;
}

const findings = [];

for (const filePath of findSourceFiles(srcDir)) {
  const content = fs.readFileSync(filePath, "utf8");
  const lines = content.split(/\r?\n/);

  lines.forEach((line, index) => {
    if (patterns.some((pattern) => pattern.test(line))) {
      const relativePath = path.relative(process.cwd(), filePath);
      findings.push(`${relativePath}:${index + 1}: ${line.trim()}`);
    }
  });
}

if (findings.length > 0) {
  console.error("Mojibake-like frontend text found:");
  for (const finding of findings) {
    console.error(finding);
  }
  process.exit(1);
}

console.log("No mojibake-like frontend text found.");
