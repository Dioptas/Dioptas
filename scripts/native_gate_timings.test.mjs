// Exercises the native gate's timing report and step sequence without Rust:
// the gate runs from a scratch copy with fake cargo/npm executables on PATH.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import {
  chmodSync,
  copyFileSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  realpathSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it } from "node:test";
import {
  coverageRequested,
  markdownSummary,
  slowestFirst,
  textSummary,
  timingReport,
} from "./native_gate_timings.mjs";

const scripts = path.dirname(fileURLToPath(import.meta.url));
const step = (name, s, status = "passed") => ({
  name,
  command: `cargo ${name}`,
  seconds: s,
  status,
});

describe("timing report", () => {
  const report = timingReport({
    steps: [step("fmt", 0.25), step("tests", 300.04), step("clippy", 100)],
    status: "passed",
    flags: ["--processor"],
    totalSeconds: 400.5,
    platform: "linux",
    arch: "x64",
  });

  it("records totals, platform and flags", () => {
    assert.equal(report.status, "passed");
    assert.equal(report.platform, "linux");
    assert.deepEqual(report.flags, ["--processor"]);
    assert.equal(report.coverage, false);
    assert.equal(report.totalSeconds, 400.5);
    assert.equal(report.stepSeconds, 400.29);
    assert.deepEqual(
      report.steps.map((s) => s.name),
      ["fmt", "tests", "clippy"],
    );
  });

  it("sorts slowest first and keeps execution order for ties", () => {
    assert.deepEqual(
      slowestFirst([step("a", 1), step("b", 2), step("c", 1)]).map(
        (s) => s.name,
      ),
      ["b", "a", "c"],
    );
  });

  it("prints an aligned text table", () => {
    const lines = textSummary(report).split("\n");
    assert.match(lines[0], /--processor; linux x64; passed; total 400\.5 s/);
    assert.deepEqual(
      lines.slice(1).map((l) => l.trim().split(/\s+/).at(-1)),
      ["tests", "clippy", "fmt"],
    );
    assert.match(lines[1], /^ {2}300\.0 s {2}74\.9% {2}passed {2}tests$/);
    assert.equal(new Set(lines.slice(1).map((l) => l.indexOf(" s "))).size, 1);
  });

  it("writes a Markdown table safe for pipes in commands", () => {
    const md = markdownSummary(
      timingReport({
        steps: [{ ...step("x", 1, "failed"), command: "a | b <c>" }],
        status: "failed",
        flags: ["--host"],
        totalSeconds: 0,
      }),
    );
    assert.match(md, /^### Native gate timings: --host; .*; failed; total/);
    assert.match(
      md,
      /\| x \| 1\.0 \| - \| failed \| <code>a \\\| b &lt;c><\/code> \|/,
    );
    assert.ok(md.endsWith("\n\n"));
  });

  it("accepts only 0 or 1 for the coverage opt-in", () => {
    assert.equal(coverageRequested(undefined), false);
    assert.equal(coverageRequested(""), false);
    assert.equal(coverageRequested("0"), false);
    assert.equal(coverageRequested("1"), true);
    assert.throws(() => coverageRequested("yes"), /must be 0 or 1/);
  });
});

// A scratch repository layout: scripts holds the real gate, its helper
// and trivial stand-ins for the two shared-boundary checks it runs first.
function scratchGate() {
  const root = realpathSync(mkdtempSync(path.join(tmpdir(), "native-gate-")));
  const own = path.join(root, "scripts");
  mkdirSync(own, { recursive: true });
  mkdirSync(path.join(root, "backend"));
  for (const file of ["check_native_desktop.mjs", "native_gate_timings.mjs"])
    copyFileSync(path.join(scripts, file), path.join(own, file));
  for (const file of [
    "check_glib_backport.mjs",
    "generate_native_contracts.mjs",
  ])
    writeFileSync(path.join(own, file), "");
  const bin = path.join(root, "bin");
  mkdirSync(bin);
  for (const tool of ["cargo", "npm"]) {
    const fake = path.join(bin, tool);
    // Log the call; fail when FAKE_FAIL occurs in the argument list.
    writeFileSync(
      fake,
      `#!/bin/sh\nprintf '%s|%s %s\\n' "$PWD" "${tool}" "$*" >> "$FAKE_LOG"\n` +
        `case " $* " in *"$FAKE_FAIL"*) [ -n "$FAKE_FAIL" ] && exit 3;; esac\nexit 0\n`,
    );
    chmodSync(fake, 0o755);
  }
  return {
    root,
    run(flags, env = {}) {
      const log = path.join(root, "calls.log");
      rmSync(log, { force: true });
      const summary = path.join(root, "step-summary.md");
      rmSync(summary, { force: true });
      const artifacts = path.join(root, "artifacts");
      rmSync(artifacts, { recursive: true, force: true });
      const r = spawnSync(
        process.execPath,
        [path.join(own, "check_native_desktop.mjs"), ...flags],
        {
          encoding: "utf8",
          env: {
            ...process.env,
            PATH: `${bin}${path.delimiter}${process.env.PATH}`,
            FAKE_LOG: log,
            FAKE_FAIL: "",
            GITHUB_STEP_SUMMARY: summary,
            DIOPTAS_GATE_COVERAGE: "",
            ...env,
          },
        },
      );
      const read = (file) =>
        existsSync(file) ? readFileSync(file, "utf8") : "";
      const timings = read(path.join(artifacts, "ci-native/timings.json"));
      return {
        ...r,
        calls: read(log)
          .split("\n")
          .filter(Boolean)
          .map((line) => {
            const [cwd, command] = line.split("|");
            return `${path.relative(root, realpathSync(cwd)) || "."}: ${command}`;
          }),
        summary: read(summary),
        timings: timings && JSON.parse(timings),
        artifacts: path.join(artifacts, "ci-native"),
      };
    },
  };
}

const processorCalls = [
  ".: cargo fmt --manifest-path backend/Cargo.toml -- --check",
  ".: cargo clippy --locked --manifest-path backend/Cargo.toml --no-default-features --all-targets -- -D warnings",
  ".: cargo test --locked --manifest-path backend/Cargo.toml --no-default-features --lib",
  ".: cargo clippy --locked --manifest-path backend/Cargo.toml --all-features --all-targets -- -D warnings",
  ".: cargo test --locked --manifest-path backend/Cargo.toml --all-features",
  ".: cargo build --locked --manifest-path backend/Cargo.toml --all-features",
];
const processorSteps = [
  "glib-security-backport",
  "native-contract-generation",
  "rust-format",
  "rust-core-clippy",
  "rust-core-tests",
  "rust-clippy",
  "rust-tests",
  "rust-build",
];

describe(
  "native gate with fake tools",
  { skip: process.platform === "win32" && "uses POSIX shell stand-ins" },
  () => {
    const gate = scratchGate();
    process.on("exit", () =>
      rmSync(gate.root, { recursive: true, force: true }),
    );

    it("keeps the processor step order and reports every step", () => {
      const r = gate.run(["--processor"]);
      assert.equal(r.status, 0, r.stderr);
      assert.deepEqual(r.calls, processorCalls);
      assert.equal(r.timings.status, "passed");
      assert.deepEqual(r.timings.flags, ["--processor"]);
      assert.equal(r.timings.coverage, false);
      assert.equal(r.timings.platform, process.platform);
      assert.deepEqual(
        r.timings.steps.map((s) => s.name),
        processorSteps,
      );
      assert.ok(r.timings.steps.every((s) => s.status === "passed"));
      assert.ok(r.timings.steps.every((s) => s.seconds >= 0));
      assert.ok(r.timings.totalSeconds >= r.timings.stepSeconds);
      assert.match(r.stdout, /rust-tests: passed in \d+\.\d s/);
      assert.match(r.stdout, /Native gate timings \(--processor; .*; passed;/);
      assert.match(r.summary, /\| rust-build \| \d+\.\d \|/);
      assert.deepEqual(
        JSON.parse(
          readFileSync(
            path.join(r.artifacts, "timings-processor.json"),
            "utf8",
          ),
        ),
        r.timings,
      );
    });

    it("reports the steps so far and exits non-zero when a step fails", () => {
      const r = gate.run(["--processor"], { FAKE_FAIL: "clippy --locked" });
      assert.notEqual(r.status, 0);
      assert.equal(r.calls.length, 2);
      assert.equal(r.timings.status, "failed");
      assert.deepEqual(
        r.timings.steps.map((s) => [s.name, s.status, s.exitCode]),
        [
          ["glib-security-backport", "passed", 0],
          ["native-contract-generation", "passed", 0],
          ["rust-format", "passed", 0],
          ["rust-core-clippy", "failed", 3],
        ],
      );
      // The summary precedes the error that stops the gate.
      const summary = r.stdout.indexOf("Native gate timings");
      assert.ok(summary > 0);
      assert.match(r.stderr, /rust-core-clippy failed \(3\) after \d+\.\d s/);
      assert.equal(r.summary.match(/### Native gate timings/g).length, 1);
      assert.match(r.summary, /\| rust-core-clippy \| .* \| failed \|/);
    });

    it("swaps only the all-features test step under the coverage opt-in", () => {
      const r = gate.run(["--processor"], { DIOPTAS_GATE_COVERAGE: "1" });
      assert.equal(r.status, 0, r.stderr);
      const tests = processorCalls.indexOf(
        ".: cargo test --locked --manifest-path backend/Cargo.toml --all-features",
      );
      assert.deepEqual(r.calls, [
        ...processorCalls.slice(0, tests),
        "backend: cargo llvm-cov --locked --all-features --lcov --output-path ../artifacts/coverage/lcov.info",
        "backend: cargo llvm-cov report --html --output-dir ../artifacts/coverage/html",
        ...processorCalls.slice(tests + 1),
      ]);
      assert.equal(r.timings.coverage, true);
      assert.deepEqual(
        r.timings.steps.map((s) => s.name),
        [
          ...processorSteps.slice(0, -1),
          "rust-coverage-html",
          processorSteps.at(-1),
        ],
      );
      assert.ok(existsSync(path.join(gate.root, "artifacts/coverage")));
    });

    it("ignores the coverage opt-in without --processor", () => {
      const r = gate.run(["--host"], { DIOPTAS_GATE_COVERAGE: "1" });
      assert.equal(r.status, 0, r.stderr);
      assert.equal(r.timings.coverage, false);
      assert.ok(!r.calls.some((c) => c.includes("llvm-cov")));
    });

    it("rejects an unclear coverage opt-in before running anything", () => {
      const r = gate.run(["--processor"], { DIOPTAS_GATE_COVERAGE: "true" });
      assert.notEqual(r.status, 0);
      assert.match(r.stderr, /DIOPTAS_GATE_COVERAGE must be 0 or 1/);
      assert.deepEqual(r.calls, []);
      assert.equal(r.timings, "");
    });

    it("times the host gate and npm steps too", () => {
      const r = gate.run(["--host"]);
      assert.equal(r.status, 0, r.stderr);
      assert.deepEqual(r.calls, [
        ".: npm run test:release-config",
        ".: npm run backend:prepare -- --debug",
        ".: npm run build",
        ".: cargo test --locked --manifest-path src-tauri/Cargo.toml",
      ]);
      assert.equal(r.timings.steps.at(-1).name, "host-tests");
      assert.ok(existsSync(path.join(r.artifacts, "timings-host.json")));
    });
  },
);
