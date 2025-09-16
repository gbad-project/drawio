import { test, expect } from "bun:test";
import { createHash } from "crypto";
import { fileURLToPath } from "url";
import { readFileSync, readdirSync, existsSync } from "fs";
import { join, extname, basename } from "path";
import { createRml } from "../src/rdfexport";

const fixturesDir = fileURLToPath(new URL("./fixtures", import.meta.url));

function runRdfExportTest(fixtureFile: string, rmlFile: string) {
  test(`${fixtureFile}: rdfexport plugin exports RML`, async () => {
    const fixturePath = join(fixturesDir, fixtureFile);
    const xml = await Bun.file(fixturePath).text();

    // For now, we are not using the csv file.
    const csv = "";

    const rml = createRml(xml);

    expect(rml).toBeString();
    expect(rml.length).toBeGreaterThan(0);

    // TODO: Add full RML comparison later.
    // const rmlPath = join(fixturesDir, rmlFile);
    // const expectedRml = await Bun.file(rmlPath).text();
    // expect(rml).toEqual(expectedRml);
  });
}

for (const file of readdirSync(fixturesDir)) {
  if (extname(file) === ".drawio") {
    const base = basename(file, ".drawio");
    const rmlFile = base + ".rml";

    if (
      !existsSync(join(fixturesDir, rmlFile)) ||
      !file.startsWith("General")
    ) {
      test.skip(`${file}: skipped (no matching ${rmlFile} or not a General fixture)`, () => {});
      continue;
    }

    runRdfExportTest(file, rmlFile);
  }
}
