import { test, expect } from "bun:test";
import * as fs from "fs";
import * as path from "path";
import { createRml } from "../src/rmlexport";
import { Store, Parser, Quad } from "n3";
import type { Term } from "n3";

const fixturesPath = path.join(import.meta.dir, "fixtures");
const files = fs.readdirSync(fixturesPath);
const drawioFiles = files.filter((file) => file.endsWith(".drawio"));

function termToString(term: Term): string {
  if (term.termType === "BlankNode") {
    return "_:b"; // Canonical representation for blank nodes
  }
  return term.value;
}

function quadToString(quad: Quad): string {
  return `${termToString(quad.subject)} ${termToString(quad.predicate)} ${termToString(quad.object)}.`;
}

function areGraphsIsomorphic(g1: Store, g2: Store): boolean {
  if (g1.size !== g2.size) {
    return false;
  }

  const g1Quads = g1.getQuads(null, null, null, null).map(quadToString).sort();
  const g2Quads = g2.getQuads(null, null, null, null).map(quadToString).sort();

  if (g1Quads.length !== g2Quads.length) return false;

  for (let i = 0; i < g1Quads.length; i++) {
    if (g1Quads[i] !== g2Quads[i]) {
      return false;
    }
  }

  return true;
}

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

    // Use the file path of the RML fixture as the base IRI for parsing.
    const baseIRI = `file://${rmlPath}`;
    const generatedStore = parseRml(rml, baseIRI);
    const expectedStore = parseRml(expectedRml, baseIRI);

    const isomorphic = areGraphsIsomorphic(generatedStore, expectedStore);

    if (!isomorphic) {
      // console.log("Generated RML:", rml);
      // console.log("Expected RML:", expectedRml);
      console.log(
        `Generated store size: ${generatedStore.size}, Expected store size: ${expectedStore.size}`,
      );
    }

    expect(isomorphic).toBe(true);
  });
}
