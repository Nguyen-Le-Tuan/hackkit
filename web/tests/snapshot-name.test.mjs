import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { snapshotName } from "../js/snapshot-name.js";

// Shared with tests/test_snapshot.py so Python and JS can never drift apart.
const cases = JSON.parse(readFileSync(new URL("./snapshot_names.json", import.meta.url)));

test("snapshotName matches the shared examples", () => {
  for (const [path, expected] of cases) assert.equal(snapshotName(path), expected, path);
});
