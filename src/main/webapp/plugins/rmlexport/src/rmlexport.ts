import { JSDOM } from "jsdom";
import {
  DataFactory,
  Writer,
  Store,
} from "n3";

const { namedNode, literal, quad, blankNode } = DataFactory;

// --- NAMESPACES and PREFIXES ---
const prefixes: { [key: string]: string } = {
  "": "https://data.archives.gov.on.test.gbad.ca/Schema/Mapping#",
  add: "https://data.archives.gov.on.test.gbad.ca/Schema/Description-Listings/",
  auth: "https://data.archives.gov.on.test.gbad.ca/Schema/Authority/",
  owl: "http://www.w3.org/2002/07/owl#",
  rdf: "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
  rdfs: "http://www.w3.org/2000/01/rdf-schema#",
  rr: "http://www.w3.org/ns/r2rml#",
  rml: "http://semweb.mmlab.be/ns/rml#",
  ql: "http://semweb.mmlab.be/ns/ql#",
  fnml: "http://semweb.mmlab.be/ns/fnml#",
  fno: "https://w3id.org/function/ontology#",
  "idlab-fn": "https://w3id.org/imec/idlab/function#",
  grel: "http://users.ugent.be/~bjdmeest/function/grel.ttl#",
  rico: "https://www.ica.org/standards/RiC/ontology#",
};

function expandPrefix(prefixedName: string): string {
    const parts = prefixedName.split(":", 2);
    if (parts.length > 1 && prefixes[parts[0]]) {
        return prefixes[parts[0]] + parts[1];
    }
    // If it's a full URL, return it as is
    if (prefixedName.startsWith("http")) {
        return prefixedName;
    }
    // Handle default prefix
    if (!prefixedName.includes(":") && prefixes[""]) {
        return prefixes[""] + prefixedName;
    }
    return prefixedName;
}

// --- RML Data Structures ---
interface LogicalSource {
  source: string;
  referenceFormulation: "CSV";
  iterator?: string;
}

interface SubjectMap {
  class: string[];
  template?: string;
  constant?: string;
  termType?: "IRI" | "BlankNode";
}

interface ObjectMap {
  reference?: string;
  template?: string;
  constant?: string;
  parentTriplesMap?: string;
  termType?: "IRI" | "Literal" | "BlankNode";
  language?: string;
}

interface PredicateObjectMap {
  predicate: string;
  objectMap: ObjectMap;
}

interface TriplesMap {
  id: string;
  logicalSource: LogicalSource;
  subjectMap: SubjectMap;
  predicateObjectMaps: PredicateObjectMap[];
}

// --- Drawio Parsing Data Structures ---
interface Individual {
  identifier: string;
  ricClass: string;
}

interface Arrow {
  identifier: string;
  source: string;
  target: string;
}

type Dimensions = [number, number, number, number]; // x, y, width, height
type Point = [number, number]; // x, y

// --- RML Generator Main Class ---
export async function createRml(
  drawioXml: string,
  sourceFilename: string,
): Promise<string> {
  const parser = new DrawioParser(drawioXml, sourceFilename);
  const triplesMaps = parser.parse();
  const serializer = new RmlSerializer(triplesMaps);
  return serializer.serialize();
}

// --- Drawio XML Parser ---
class DrawioParser {
  private dom: JSDOM;
  private doc: Document;
  private cells: { [id: string]: Element } = {};
  private individuals: { cell: Element; individual: Individual, dimensions: Dimensions }[] = [];
  private arrows: { cell: Element, start: Point | null, end: Point | null, label: string }[] = [];
  private literals: { cell: Element, dimensions: Dimensions }[] = [];


  constructor(
    private xmlString: string,
    private sourceFilename: string,
  ) {
    this.dom = new JSDOM(xmlString, { contentType: "application/xml" });
    this.doc = this.dom.window.document;
    this._extractCells();
    this._extractIndividualAndArrowAndLiteralCells();
  }

  private _extractCells(): void {
    const cellElements = Array.from(this.doc.querySelectorAll("mxCell"));
    for (const cell of cellElements) {
      const id = cell.getAttribute("id");
      if (id) {
        this.cells[id] = cell;
      }
    }
  }

  private _getCellValue(cell: Element): string {
    const value = cell.getAttribute("value") || "";
    if (!value) {
      return "";
    }
    try {
      const tempDiv = this.doc.createElement('div');
      tempDiv.innerHTML = value;
      return (tempDiv.textContent || "").trim();
    } catch (e) {
      // Fallback for malformed HTML, similar to Python's lenient parser
      return value.replace(/<[^>]*>/g, ' ').replace(/\s\s+/g, ' ').trim();
    }
  }

  private _getCellById(id: string): Element | undefined {
    return this.cells[id];
  }

  private _getParent(cell: Element): Element | undefined {
    const parentId = cell.getAttribute("parent");
    return parentId ? this._getCellById(parentId) : undefined;
  }

  private _getGeometry(cell: Element): Element | undefined {
    return Array.from(cell.children).find(child => child.tagName === 'mxGeometry');
  }

  private _getDimensions(cell: Element): Dimensions | null {
    const geo = this._getGeometry(cell);
    if (!geo) return null;
    const x = parseFloat(geo.getAttribute("x") || "0");
    const y = parseFloat(geo.getAttribute("y") || "0");
    const width = parseFloat(geo.getAttribute("width") || "0");
    const height = parseFloat(geo.getAttribute("height") || "0");
    return [x, y, width, height];
  }

  private _getArrowEndpoint(arrowCell: Element, type: 'source' | 'target'): Point | null {
    const geo = this._getGeometry(arrowCell);
    if (!geo) return null;

    const point = Array.from(geo.children).find(child => child.tagName === 'mxPoint' && child.getAttribute('as') === `${type}Point`);
    if (point) {
        let x = parseFloat(point.getAttribute('x') || '0');
        let y = parseFloat(point.getAttribute('y') || '0');

        let parent = this._getParent(arrowCell);
        while(parent && parent.getAttribute('id') !== '1') {
            const parentGeo = this._getGeometry(parent);
            if(parentGeo) {
                x += parseFloat(parentGeo.getAttribute('x') || '0');
                y += parseFloat(parentGeo.getAttribute('y') || '0');
            }
            parent = this._getParent(parent);
        }

        return [x, y];
    }
    return null;
  }

  private _extractIndividualAndArrowAndLiteralCells(): void {
    for (const id in this.cells) {
      if (id === "0" || id === "1") continue;
      const cell = this.cells[id];
      const value = this._getCellValue(cell);

      // Arrow detection
      if(cell.hasAttribute('edge')) {
        const childLabelCell = Array.from(cell.children).find(c => this._getCellValue(c) !== '');
        const label = this._getCellValue(childLabelCell || cell);
        if (label) {
            this.arrows.push({
                cell,
                start: this._getArrowEndpoint(cell, 'source'),
                end: this._getArrowEndpoint(cell, 'target'),
                label
            });
        }
        continue;
      }

      const prefixesInValue = Object.keys(prefixes).filter(p => p && value.startsWith(p + ':'));
      if (prefixesInValue.length > 0) {
        const parent = this._getParent(cell);
        if (parent) {
          const individualIdentifier = this._getCellValue(parent);
          if (individualIdentifier) {
            const parentDimensions = this._getDimensions(parent);
            if(parentDimensions) {
                const ricClasses = value.split(' ').map(s => s.trim()).filter(s => s.includes(':'));
                for(const ricClass of ricClasses) {
                    this.individuals.push({
                        cell: cell,
                        individual: { identifier: individualIdentifier, ricClass: ricClass },
                        dimensions: parentDimensions,
                    });
                }
            }
          }
        }
      } else { // Potential literal
        const style = cell.getAttribute('style') || '';
        if(style.includes('rounded=1') && cell.getAttribute('parent') === '1') {
            const dims = this._getDimensions(cell);
            if (dims) {
                this.literals.push({ cell, dimensions: dims });
            }
        }
      }
    }
  }

  private _isCloseEnough(point: Point, dims: Dimensions, maxGap: number = 10): boolean {
    const [px, py] = point;
    const [dx, dy, dw, dh] = dims;
    return px >= dx - maxGap && px <= dx + dw + maxGap &&
           py >= dy - maxGap && py <= dy + dh + maxGap;
  }

  private _findClosestCell(point: Point): Element | null {
    // Check individuals first
    for(const { cell: indCell, dimensions: indDims } of this.individuals) {
        const parent = this._getParent(indCell);
        if (parent && this._isCloseEnough(point, indDims)) {
            return parent;
        }
    }
    // Check literals
    for(const { cell: litCell, dimensions: litDims } of this.literals) {
        if(this._isCloseEnough(point, litDims)) {
            return litCell;
        }
    }
    return null;
  }


  private * _yieldIndividualsAndArrows(): Generator<Individual | Arrow> {
    const yieldedIdentifiers = new Set<string>();
    for (const { individual } of this.individuals) {
        const key = `${individual.identifier}-${individual.ricClass}`;
        if (!yieldedIdentifiers.has(key)) {
            yield individual;
            yieldedIdentifiers.add(key);
        }
    }

    for (const arrowData of this.arrows) {
        let sourceCellId = arrowData.cell.getAttribute('source');
        let targetCellId = arrowData.cell.getAttribute('target');

        let sourceCell = sourceCellId ? this._getCellById(sourceCellId) : null;
        let targetCell = targetCellId ? this._getCellById(targetCellId) : null;

        if (!sourceCell && arrowData.start) {
            sourceCell = this._findClosestCell(arrowData.start);
        }
        if (!targetCell && arrowData.end) {
            targetCell = this._findClosestCell(arrowData.end);
        }

        if (sourceCell && targetCell) {
            const sourceName = this._getCellValue(sourceCell);
            const targetName = this._getCellValue(targetCell);

            yield {
                identifier: arrowData.label,
                source: sourceName,
                target: targetName
            };
        }
    }
  }

  private _cleanForId(id: string): string {
    let de_prefixed = id;
    if (de_prefixed.startsWith("rr:template=")) {
        de_prefixed = de_prefixed.substring("rr:template=".length);
    } else if (de_prefixed.startsWith("rr:constant=")) {
        de_prefixed = de_prefixed.substring("rr:constant=".length);
    } else if (de_prefixed.startsWith("rml:reference=")) {
        de_prefixed = de_prefixed.substring("rml:reference=".length);
    }

    // Replace invalid characters with underscore
    return de_prefixed.replace(/[^a-zA-Z0-9_-]/g, '_');
  }

  public parse(): TriplesMap[] {
    const blocks: { [key: string]: { types: Set<string>, facts: { [predicate: string]: Set<string> } } } = {};

    for (const item of this._yieldIndividualsAndArrows()) {
        if ('ricClass' in item) { // It's an Individual
            const { identifier, ricClass } = item;
            if (!blocks[identifier]) {
                blocks[identifier] = { types: new Set(), facts: {} };
            }
            blocks[identifier].types.add(ricClass);
        } else { // It's an Arrow
            const { identifier, source, target } = item;
            if (!blocks[source]) {
                blocks[source] = { types: new Set(), facts: {} };
            }
            if (!blocks[source].facts[identifier]) {
                blocks[source].facts[identifier] = new Set();
            }
            blocks[source].facts[identifier].add(target);
        }
    }

    const triplesMaps: TriplesMap[] = [];
    for (const identifier in blocks) {
        const block = blocks[identifier];
        const subjectMap: SubjectMap = { class: Array.from(block.types) };

        if (identifier.startsWith("rr:template=")) {
            subjectMap.template = identifier.substring("rr:template=".length);
        } else if (identifier.startsWith("rr:constant=")) {
            subjectMap.constant = identifier.substring("rr:constant=".length);
        } else {
            subjectMap.template = identifier; // Default to template
        }

        const predicateObjectMaps: PredicateObjectMap[] = [];
        for(const predicate in block.facts) {
            for(const object of block.facts[predicate]) {
                let objectMap: ObjectMap = {};
                if(blocks[object]) { // It's another individual
                    objectMap.parentTriplesMap = this._cleanForId(object);
                } else { // It's a literal
                    if (object.startsWith("rml:reference=")) {
                        objectMap.reference = object.substring("rml:reference=".length);
                    } else if (object.startsWith("rr:template=")) {
                        objectMap.template = object.substring("rr:template=".length);
                    } else if (object.startsWith("rr:constant=")) {
                        objectMap.constant = object.substring("rr:constant=".length);
                    } else {
                        objectMap.constant = object;
                        objectMap.termType = 'Literal';
                    }
                }
                predicateObjectMaps.push({ predicate, objectMap });
            }
        }

        triplesMaps.push({
            id: this._cleanForId(identifier),
            logicalSource: {
                source: this.sourceFilename,
                referenceFormulation: "CSV",
            },
            subjectMap,
            predicateObjectMaps
        });
    }

    return triplesMaps;
  }
}


// --- RML Serializer ---
class RmlSerializer {
  private writer: Writer;
  private store: Store;

  constructor(private triplesMaps: TriplesMap[]) {
    this.store = new Store();
    this.writer = new Writer({ prefixes });
  }

  private _createNode(value: string) {
      if(value.startsWith('_:')) {
          return blankNode(value.substring(2));
      }
      return namedNode(expandPrefix(value));
  }

  public serialize(): Promise<string> {
    for (const tm of this.triplesMaps) {
      const tmNode = this._createNode(tm.id);
      this.store.addQuad(
        tmNode,
        namedNode(expandPrefix("rdf:type")),
        namedNode(expandPrefix("rr:TriplesMap")),
      );

      const lsNode = blankNode();
      this.store.addQuad(
        tmNode,
        namedNode(expandPrefix("rml:logicalSource")),
        lsNode,
      );
      this.store.addQuad(
        lsNode,
        namedNode(expandPrefix("rml:source")),
        literal(tm.logicalSource.source),
      );
      this.store.addQuad(
        lsNode,
        namedNode(expandPrefix("rml:referenceFormulation")),
        namedNode(expandPrefix("ql:CSV")),
      );
      if (tm.logicalSource.iterator) {
        this.store.addQuad(
          lsNode,
          namedNode(expandPrefix("rml:iterator")),
          literal(tm.logicalSource.iterator),
        );
      }

      const smNode = blankNode();
      this.store.addQuad(
        tmNode,
        namedNode(expandPrefix("rr:subjectMap")),
        smNode,
      );
      tm.subjectMap.class.forEach((c) => {
        this.store.addQuad(
          smNode,
          namedNode(expandPrefix("rr:class")),
          this._createNode(c),
        );
      });
      if (tm.subjectMap.template) {
        this.store.addQuad(
          smNode,
          namedNode(expandPrefix("rr:template")),
          literal(tm.subjectMap.template),
        );
      }
      if (tm.subjectMap.constant) {
        this.store.addQuad(
          smNode,
          namedNode(expandPrefix("rr:constant")),
          this._createNode(tm.subjectMap.constant),
        );
      }
      if (tm.subjectMap.termType) {
        this.store.addQuad(
          smNode,
          namedNode(expandPrefix("rr:termType")),
          namedNode(expandPrefix("rr:" + tm.subjectMap.termType)),
        );
      }

      for (const pom of tm.predicateObjectMaps) {
        const pomNode = blankNode();
        this.store.addQuad(
          tmNode,
          namedNode(expandPrefix("rr:predicateObjectMap")),
          pomNode,
        );
        this.store.addQuad(
            pomNode,
            namedNode(expandPrefix("rr:predicate")),
            this._createNode(pom.predicate),
        );

        const omNode = blankNode();
        this.store.addQuad(
          pomNode,
          namedNode(expandPrefix("rr:objectMap")),
          omNode,
        );

        if (pom.objectMap.parentTriplesMap) {
          this.store.addQuad(
            omNode,
            namedNode(expandPrefix("rr:parentTriplesMap")),
            this._createNode(pom.objectMap.parentTriplesMap),
          );
        } else if (pom.objectMap.reference) {
          this.store.addQuad(
            omNode,
            namedNode(expandPrefix("rml:reference")),
            literal(pom.objectMap.reference),
          );
        } else if (pom.objectMap.template) {
          this.store.addQuad(
            omNode,
            namedNode(expandPrefix("rr:template")),
            literal(pom.objectMap.template),
          );
        } else if (pom.objectMap.constant) {
          const term =
            pom.objectMap.termType === "Literal"
              ? literal(pom.objectMap.constant, pom.objectMap.language)
              : this._createNode(pom.objectMap.constant);
          this.store.addQuad(
            omNode,
            namedNode(expandPrefix("rr:constant")),
            term,
          );
        }
        if (pom.objectMap.termType) {
          this.store.addQuad(
            omNode,
            namedNode(expandPrefix("rr:termType")),
            namedNode(expandPrefix("rr:" + pom.objectMap.termType)),
          );
        }
      }
    }

    return new Promise((resolve, reject) => {
      this.writer.addQuads(this.store.getQuads(null, null, null, null));
      this.writer.end((error, result) => {
        if (error) {
          reject(error);
        } else {
          // The base IRI is now handled in the test file, so we don't add it here.
          resolve(result);
        }
      });
    });
  }
}
