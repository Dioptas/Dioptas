import assert from "node:assert/strict";
import {
  appendFile,
  mkdir,
  mkdtemp,
  readFile,
  rm,
  writeFile,
} from "node:fs/promises";
import path from "node:path";
import { tmpdir } from "node:os";
import { test } from "node:test";
import { readDmgRecovery, finishDmgRecovery } from "./resume_macos_dmg.mjs";
import { version } from "./release_config.mjs";
const source = "a".repeat(40),
  packaging = "b".repeat(40);
const target = "x86_64-apple-darwin",
  id = "d88ccef8-bb6d-45bf-bfea-08e05869641c";
async function fixture(run) {
  const root = await mkdtemp(path.join(tmpdir(), "dioptas-dmg-resume-"));
  const directory = path.join(root, "original"),
    logs = path.join(directory, "dist/notarization");
  await mkdir(logs, { recursive: true });
  const dmg = path.join(directory, `Dioptas-Desktop_${version}_macos_x64.dmg`);
  await writeFile(dmg, "original signed bytes");
  const idPath = path.join(logs, path.basename(dmg) + "-submission-id.txt");
  await writeFile(idPath, id + "\n");
  const metadata = {
    name: "Native macOS artifacts (no publishing)",
    id: 123,
    head_sha: source,
  };
  try {
    await run({ root, directory, dmg, idPath, metadata });
  } finally {
    await rm(root, { recursive: true, force: true });
  }
}
test("recovery binds the original DMG, submission ID and app source", () =>
  fixture(async ({ root, dmg, metadata }) => {
    const recovery = await readDmgRecovery(root, metadata, target);
    assert.equal(recovery.dmg, dmg);
    assert.equal(recovery.submissionId, id);
    assert.equal(recovery.sourceRevision, source);
  }));
test("a resumed packaging run retains the original app revision", () =>
  fixture(async ({ root, directory, metadata }) => {
    await writeFile(
      path.join(directory, "source.json"),
      JSON.stringify({ sourceRevision: source, target, version }),
    );
    const result = await readDmgRecovery(
      root,
      { ...metadata, head_sha: packaging },
      target,
    );
    assert.equal(result.sourceRevision, source);
    await writeFile(
      path.join(directory, "source.json"),
      JSON.stringify({
        sourceRevision: source,
        target: "aarch64-apple-darwin",
        version,
      }),
    );
    await assert.rejects(readDmgRecovery(root, metadata, target));
  }));
test("missing/malformed submission IDs and ambiguous images fail closed", () =>
  fixture(async ({ root, dmg, idPath, metadata }) => {
    await writeFile(idPath, "not-a-submission");
    await assert.rejects(
      readDmgRecovery(root, metadata, target),
      /Invalid original submission ID/,
    );
    await rm(idPath);
    await assert.rejects(readDmgRecovery(root, metadata, target), /ENOENT/);
    await writeFile(idPath, id);
    const other = path.join(root, "other");
    await mkdir(other);
    await writeFile(path.join(other, path.basename(dmg)), "other bytes");
    await assert.rejects(
      readDmgRecovery(root, metadata, target),
      /exactly one original signed DMG/,
    );
  }));
test("resume uses the original ID and preserves its input before installed verification", () =>
  fixture(async ({ root, dmg, metadata }) => {
    const recovery = await readDmgRecovery(root, metadata, target),
      calls = [],
      output = path.join(root, "resumed");
    const report = await finishDmgRecovery({
      recovery,
      output,
      target,
      teamIdentifier: "ABCD123456",
      packagingRevision: packaging,
      sourceDirty: false,
      run: async (command, args) => {
        calls.push([command, ...args]);
        assert.equal(command, "python3");
        assert.deepEqual(args.slice(-2), ["--submission-id", id]);
        assert.equal(await readFile(args[2], "utf8"), "original signed bytes");
        await appendFile(args[2], " + Apple ticket");
      },
      verify: async (file, options) => {
        assert.equal(options.notarized, true);
        assert.equal(options.nativeSmoke, true);
        assert.equal(
          await readFile(file, "utf8"),
          "original signed bytes + Apple ticket",
        );
        await writeFile(options.archivePath, "verified signed app archive");
        return {
          copiedInstallation: true,
          nativeWebKit: true,
          notarized: true,
        };
      },
    });
    assert.equal(calls.length, 1);
    assert.equal(await readFile(dmg, "utf8"), "original signed bytes");
    assert.equal(report.sourceRevision, source);
    assert.equal(report.packagingRevision, packaging);
    assert.equal(report.notarizationSubmissionId, id);
    assert.equal(report.published, false);
    assert.equal(report.recoveredDmg, true);
    assert(
      (await readFile(path.join(output, "SHA256SUMS"), "utf8")).includes(
        ".app.tar.gz",
      ),
    );
  }));
test("failed installed verification cannot create a qualified build report", () =>
  fixture(async ({ root, metadata }) => {
    const recovery = await readDmgRecovery(root, metadata, target),
      output = path.join(root, "failed");
    await assert.rejects(
      finishDmgRecovery({
        recovery,
        output,
        target,
        teamIdentifier: "ABCD123456",
        packagingRevision: packaging,
        sourceDirty: false,
        run: async () => {},
        verify: async () => {
          throw Error("native verification failed");
        },
      }),
      /native verification failed/,
    );
    await assert.rejects(readFile(path.join(output, "build.json")), /ENOENT/);
  }));
