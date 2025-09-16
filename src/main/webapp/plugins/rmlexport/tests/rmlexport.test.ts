import { test, expect } from "bun:test";
import * as fs from "fs";
import * as path from "path";
import { createRml } from "../src/rmlexport";
import { Store, Parser } from "n3";
import { isomorphic } from "rdf-isomorphic";

const fixturesPath = path.join(import.meta.dir, "fixtures");
const files = fs.readdirSync(fixturesPath);
const drawioFiles = files.filter((file) => file.endsWith(".drawio"));

function parseRml(rml: string, baseIRI: string): Store {
  const store = new Store();
  // The baseIRI is important for resolving relative URIs in the Turtle file
  const parser = new Parser({ baseIRI });
  try {
    store.addQuads(parser.parse(rml));
  } catch (e) {
    console.error("Failed to parse RML:", rml);
    throw e;
  }
  return store;
}

for (const file of drawioFiles) {
  test(`${file}: rdfexport plugin exports RML`, async () => {
    const drawioPath = path.join(fixturesPath, file);
    const drawioContent = fs.readFileSync(drawioPath, "utf-8");

    const csvFile = file.replace(".drawio", ".csv");

    let rmlPath = path.join(fixturesPath, file.replace(".drawio", ".rml"));
    if (!fs.existsSync(rmlPath)) {
      rmlPath = path.join(fixturesPath, file.replace(".drawio", ".rdf"));
    }
    const expectedRml = fs.readFileSync(rmlPath, "utf-8");

    const rml = await createRml(drawioContent, csvFile);
    fs.writeFileSync(path.join(fixturesPath, "generated.rml"), rml);

    // Use the file path of the RML fixture as the base IRI for parsing.
    const baseIRI = `file://${rmlPath}`;
    const generatedStore = parseRml(rml, baseIRI);
    const expectedStore = parseRml(expectedRml, baseIRI);

    const expectedQuads = expectedStore.getQuads(null, null, null, null);
    const generatedQuads = generatedStore.getQuads(null, null, null, null);
    const areIsomorphic = isomorphic(expectedQuads, generatedQuads);

    if (!areIsomorphic) {
      // console.log("Generated RML:", rml);
      // console.log("Expected RML:", expectedRml);
      console.log(
        `Generated store size: ${generatedQuads.length}, Expected store size: ${expectedQuads.length}`,
      );
    }

    expect(areIsomorphic).toBe(true);
  });
}
