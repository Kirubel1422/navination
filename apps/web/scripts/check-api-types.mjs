// Fails when src/lib/api/schema.gen.ts does not match contracts/openapi.json.
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const out = join(mkdtempSync(join(tmpdir(), "navination-types-")), "schema.gen.ts");
execFileSync(
  process.execPath,
  [join(root, "node_modules/openapi-typescript/bin/cli.js"), join(root, "../../contracts/openapi.json"), "-o", out],
  { stdio: "ignore" },
);
const committed = readFileSync(join(root, "src/lib/api/schema.gen.ts"), "utf8");
if (readFileSync(out, "utf8") !== committed) {
  console.error("src/lib/api/schema.gen.ts is out of date. Run: pnpm api:types");
  process.exit(1);
}
console.log("API types match contracts/openapi.json.");
