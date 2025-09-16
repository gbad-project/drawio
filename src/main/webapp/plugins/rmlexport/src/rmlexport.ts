import { JSDOM } from "jsdom";
import {
  DataFactory,
  Writer,
  Store,
  Term,
} from "n3";
import { v5 as uuidv5 } from 'uuid';

const { namedNode, literal, quad, blankNode } = DataFactory;

// --- CONSTANTS ---
const MAPPING_NS_URL = 'https://data.archives.gov.on.test.gbad.ca/Schema/Mapping#';
const NAMESPACE_URL = '6ba7b811-9dad-11d1-80b4-00c04fd430c8';

// --- NAMESPACES and PREFIXES ---
const prefixes: { [key: string]: string } = {
  "": MAPPING_NS_URL,
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
    if (prefixedName.startsWith("http")) {
        return prefixedName;
    }
    if (!prefixedName.includes(":") && prefixes[""]) {
        return prefixes[""] + prefixedName;
    }
    return prefixedName;
}

// --- RML Data Structures ---
interface LogicalSource {
  source: string;
  referenceFormulation: "CSV";
}

interface SubjectMap {
  class: string[];
  template?: string;
  constant?: string;
  termType?: "IRI" | "BlankNode";
  mnemonic?: string;
}

interface ObjectMap {
  reference?: string;
  template?: string;
  constant?: string;
  parentTriplesMap?: string;
  termType?: "IRI" | "Literal" | "BlankNode";
  language?: string;
  mnemonic?: string;
}

interface PredicateObjectMap {
  predicate: string;
  objectMap: ObjectMap;
}

interface TriplesMap {
  id: string;
  uuid: string;
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

type Dimensions = [number, number, number, number];
type Point = [number, number];

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
    if (!value) return "";
    let textContent = "";
    try {
      const tempDiv = this.doc.createElement('div');
      tempDiv.innerHTML = value;
      textContent = tempDiv.textContent || "";
    } catch (e) {
      textContent = value.replace(/<[^>]*>/g, ' ');
    }
    // 1. Replace all whitespace sequences with a single space.
    // 2. Trim leading/trailing whitespace.
    // 3. Remove leading/trailing quotes.
    // 4. Trim again in case there was whitespace around the quotes.
    const cleaned = textContent.replace(/\s+/g, ' ').trim();
    return cleaned.replace(/^"|"$/g, '').trim();
  }

  private _getCellById(id: string): Element | undefined { return this.cells[id]; }
  private _getParent(cell: Element): Element | undefined {
    const parentId = cell.getAttribute("parent");
    return parentId ? this._getCellById(parentId) : undefined;
  }
  private _getGeometry(cell: Element): Element | undefined { return Array.from(cell.children).find(child => child.tagName === 'mxGeometry'); }
  private _getDimensions(cell: Element): Dimensions | null {
    const geo = this._getGeometry(cell);
    if (!geo) return null;
    return [
      parseFloat(geo.getAttribute("x") || "0"),
      parseFloat(geo.getAttribute("y") || "0"),
      parseFloat(geo.getAttribute("width") || "0"),
      parseFloat(geo.getAttribute("height") || "0"),
    ];
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
      if(cell.hasAttribute('edge')) {
        const childLabelCell = Array.from(cell.children).find(c => this._getCellValue(c) !== '');
        const label = this._getCellValue(childLabelCell || cell);
        if (label) {
            this.arrows.push({ cell, start: this._getArrowEndpoint(cell, 'source'), end: this._getArrowEndpoint(cell, 'target'), label });
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
                    this.individuals.push({ cell, individual: { identifier: individualIdentifier, ricClass: ricClass }, dimensions: parentDimensions });
                }
            }
          }
        }
      } else {
        const style = cell.getAttribute('style') || '';
        if(style.includes('rounded=1') && cell.getAttribute('parent') === '1') {
            const dims = this._getDimensions(cell);
            if (dims) this.literals.push({ cell, dimensions: dims });
        }
      }
    }
  }
  private _isCloseEnough(point: Point, dims: Dimensions, maxGap: number = 10): boolean {
    const [px, py] = point;
    const [dx, dy, dw, dh] = dims;
    return px >= dx - maxGap && px <= dx + dw + maxGap && py >= dy - maxGap && py <= dy + dh + maxGap;
  }
  private _findClosestCell(point: Point): Element | null {
    // For individuals, the dimensions are of the parent, but the cell is the child.
    // We need to check against the parent's dimensions but return the parent cell.
    for(const { cell: indCell, dimensions: indDims } of this.individuals) {
        const parent = this._getParent(indCell);
        if (parent && this._isCloseEnough(point, indDims)) return parent;
    }
    for(const { cell: litCell, dimensions: litDims } of this.literals) {
        if(this._isCloseEnough(point, litDims)) return litCell;
    }
    return null;
  }
  private _getSourceOrTargetIdentifier(cell: Element): string {
    const value = this._getCellValue(cell);
    const prefixesInValue = Object.keys(prefixes).filter(p => p && value.startsWith(p + ':'));

    if (prefixesInValue.length > 0) {
        // This cell defines the class, the identifier is in the parent.
        const parent = this._getParent(cell);
        return parent ? this._getCellValue(parent) : "";
    }

    // This cell is likely the parent box of an individual, or a literal box.
    // Its value is the identifier.
    return value;
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
        if (!sourceCell && arrowData.start) sourceCell = this._findClosestCell(arrowData.start);
        if (!targetCell && arrowData.end) targetCell = this._findClosestCell(arrowData.end);

        if (sourceCell && targetCell) {
            const sourceName = this._getSourceOrTargetIdentifier(sourceCell);
            const targetName = this._getSourceOrTargetIdentifier(targetCell);
            const isSourceIndividual = this.individuals.some(i => i.individual.identifier === sourceName);

            if (sourceName && targetName && isSourceIndividual) {
                yield { identifier: arrowData.label, source: sourceName, target: targetName };
            }
        }
    }
  }
  private _cleanForId(id: string): string {
    const de_prefixed = id.startsWith("rr:template=") ? id.substring("rr:template=".length)
                    : id.startsWith("rr:constant=") ? id.substring("rr:constant=".length)
                    : id.startsWith("rml:reference=") ? id.substring("rml:reference=".length)
                    : id;
    return de_prefixed.replace(/[^a-zA-Z0-9_-]/g, '_');
  }
  private _disaggregate(value: string): string[] {
    const allMatchesRegex = /\{([^}]+?)\}/g;
    const matches = value.match(allMatchesRegex);

    if (matches) {
      for (const match of matches) {
        const innerContent = match.substring(1, match.length - 1);
        const iteratorRegex = /(\d+)\.\.(\d+)/;
        const iteratorMatch = innerContent.match(iteratorRegex);

        if (iteratorMatch) {
          const [iteratorFullMatch, startStr, endStr] = iteratorMatch;
          const start = parseInt(startStr, 10);
          const end = parseInt(endStr, 10);
          const results: string[] = [];

          for (let i = start; i <= end; i++) {
            const newInnerContent = innerContent.replace(iteratorFullMatch, i.toString());
            const newValue = value.replace(match, `{${newInnerContent}}`);
            results.push(...this._disaggregate(newValue));
          }
          return results;
        }
      }
    }

    const refdFileMask = "{REFD_FILE}";
    if (value.includes(refdFileMask)) {
        return [value.replace(refdFileMask, "{REFD}"), value.replace(refdFileMask, "{REF_FILE}")];
    }

    return [value];
  }
  private _extractMnemonic(template: string | undefined): string | undefined {
    if (!template) return undefined;
    // Python regex: r"\{([A-Z:_\d\.]+)\}"
    const match = template.match(/\{([A-Z:_0-9\.]+)\}/);
    return match ? match[1] : undefined;
  }
  private _decamelize(s: string): string {
    const camelCasePattern = /(?<=[a-z])(?=[A-Z])/g;
    s = s.replace(camelCasePattern, ' ');
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  private _prettifyRdfsLabel(value: string): string {
    let pretty = value;
    try {
        pretty = decodeURIComponent(pretty);
    } catch (e) { /* ignore */ }

    const baseUri = "https://data.archives.gov.on.test.gbad.ca/";
    if (pretty.startsWith(baseUri)) {
        pretty = pretty.substring(baseUri.length);
    }
    if (pretty.startsWith('/')) {
        pretty = pretty.substring(1);
    }

    const schemaTerm = 'Schema';
    const kbTerm = 'KB';
    const schemaRegex = new RegExp(`^(${schemaTerm}|Description-Listings|Authority|Mapping)\/([A-Za-z_]+)(#.*|\/.*)?$`, 'i');

    if (pretty.toLowerCase().startsWith(schemaTerm.toLowerCase() + '/')) {
        pretty = pretty.substring(schemaTerm.length + 1);
        const match = pretty.match(schemaRegex);
        if (match) {
            const ricoClassIshTerm = this._decamelize(match[2]);
            const lastTerm = match[3];
            if (!lastTerm) {
                pretty = ricoClassIshTerm;
            } else if (lastTerm.startsWith('#')) {
                pretty = `${ricoClassIshTerm}: ${lastTerm.substring(1)}`;
            } else if (lastTerm.startsWith('/')) {
                pretty = lastTerm.substring(1);
            }
        }
    }

    if (pretty.toLowerCase().startsWith(kbTerm.toLowerCase() + '/')) {
        pretty = pretty.substring(kbTerm.length + 1);
        const mnemonicRegex = /([a-zA-Z]+)\/(\{([^}]+)\})\/?(.*)/;
        const match = pretty.match(mnemonicRegex);
        if (match) {
            const ricoIshClass = this._decamelize(match[1]);
            const mnemonicMask = match[2];
            const optionalRest = match[4];
            pretty = `${mnemonicMask} (${ricoIshClass})`;
            if (optionalRest) {
                pretty = `${mnemonicMask} (${ricoIshClass} - ${optionalRest})`;
            }
        }
    }

    return pretty;
  }
  private * _yieldTriples(): Generator<{subject: string, predicate: string, object: string}> {
    for (const item of this._yieldIndividualsAndArrows()) {
      if ('ricClass' in item) {
        // console.log("yielded individual:", item);
        yield { subject: item.identifier, predicate: "rdf:type", object: item.ricClass };
      } else {
        // console.log("yielded arrow:", item);
        yield { subject: item.source, predicate: item.identifier, object: item.target };
      }
    }
  }

  private _disaggregate_triples(triple: {subject: string, predicate: string, object: string}): {subject: string, predicate: string, object: string}[] {
    const disaggregatedSubjects = this._disaggregate(triple.subject);
    const disaggregatedObjects = this._disaggregate(triple.object);
    const results: {subject: string, predicate: string, object: string}[] = [];

    for (const subject of disaggregatedSubjects) {
      for (const object of disaggregatedObjects) {
        results.push({ subject, predicate: triple.predicate, object });
      }
    }
    return results;
  }

  public parse(): TriplesMap[] {
    const disaggregatedTriples: {subject: string, predicate: string, object: string}[] = [];
    for (const triple of this._yieldTriples()) {
      disaggregatedTriples.push(...this._disaggregate_triples(triple));
    }
    // console.log("disaggregatedTriples:", disaggregatedTriples);

    const blocks: { [key: string]: { types: Set<string>, facts: { [predicate: string]: Set<string> } } } = {};
    for (const triple of disaggregatedTriples) {
      if (triple.predicate === 'rdf:type') {
        if (!blocks[triple.subject]) blocks[triple.subject] = { types: new Set(), facts: {} };
        blocks[triple.subject].types.add(triple.object);
      } else {
        if (!blocks[triple.subject]) blocks[triple.subject] = { types: new Set(), facts: {} };
        if (!blocks[triple.subject].facts[triple.predicate]) {
            blocks[triple.subject].facts[triple.predicate] = new Set();
        }
        blocks[triple.subject].facts[triple.predicate].add(triple.object);
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
        } else if (identifier.startsWith("rml:reference=")) {
            // This is unlikely for a subject, but we can handle it.
            subjectMap.template = `{${identifier.substring("rml:reference=".length)}}`;
        } else {
            subjectMap.template = identifier;
        }
        subjectMap.termType = "IRI"; // Subjects are always IRIs
        subjectMap.mnemonic = this._extractMnemonic(subjectMap.template);

        const predicateObjectMaps: PredicateObjectMap[] = [];
        for(const predicate in block.facts) {
            for(const object of block.facts[predicate]) {
                let objectMap: ObjectMap = {};
                if(blocks[object]) {
                    objectMap.parentTriplesMap = this._cleanForId(object);
                    objectMap.termType = "IRI";
                } else {
                    if (object.startsWith("rml:reference=")) {
                        objectMap.reference = object.substring("rml:reference=".length);
                        objectMap.mnemonic = objectMap.reference;
                    } else if (object.startsWith("rr:template=")) {
                        objectMap.template = object.substring("rr:template=".length);
                        objectMap.mnemonic = this._extractMnemonic(objectMap.template);
                    } else if (object.startsWith("rr:constant=")) {
                        objectMap.constant = object.substring("rr:constant=".length);
                        const isIRI = objectMap.constant.includes(':') || objectMap.constant.startsWith("http");
                        if (isIRI) {
                            objectMap.termType = 'IRI';
                        } else {
                            objectMap.termType = 'Literal';
                        }
                    } else {
                        objectMap.constant = object;
                        objectMap.termType = 'Literal';
                    }
                }
                predicateObjectMaps.push({ predicate, objectMap });
            }
        }
        const hasRdfsLabel = predicateObjectMaps.some(pom => pom.predicate === 'rdfs:label');
        if (!hasRdfsLabel) {
            const prettyLabel = this._prettifyRdfsLabel(subjectMap.template || subjectMap.constant || '');
            if(prettyLabel) {
              predicateObjectMaps.push({ predicate: 'rdfs:label', objectMap: { template: prettyLabel, termType: 'Literal' } });
            }
        }
        const tmId = this._cleanForId(identifier);
        const fullUri = MAPPING_NS_URL + tmId;
        const tmUuid = uuidv5(fullUri, NAMESPACE_URL);

        triplesMaps.push({
            id: tmId,
            uuid: tmUuid,
            logicalSource: {
                source: this.sourceFilename,
                referenceFormulation: "CSV"
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
      if(value.startsWith('_:')) return blankNode(value.substring(2));
      return namedNode(expandPrefix(value));
  }
  private _addFnoMapValueUnlessIsNull(subject: Term, returnTuple: [Term, Term], inputTuples: [Term, Term][]): void {
    const [returnPredicate, returnObject] = returnTuple;
    const fnoWrapper = blankNode();
    this.store.addQuad(subject, namedNode(expandPrefix("fnml:functionValue")), fnoWrapper);
    const controlsIfPomap = blankNode();
    this.store.addQuad(fnoWrapper, namedNode(expandPrefix("rr:predicateObjectMap")), controlsIfPomap);
    this.store.addQuad(controlsIfPomap, namedNode(expandPrefix("rr:predicate")), namedNode(expandPrefix("fno:executes")));
    const controlsIfOmap = blankNode();
    this.store.addQuad(controlsIfPomap, namedNode(expandPrefix("rr:objectMap")), controlsIfOmap);
    this.store.addQuad(controlsIfOmap, namedNode(expandPrefix("rr:constant")), namedNode(expandPrefix("grel:controls_if")));
    const mnemonicIsNullPomap = blankNode();
    this.store.addQuad(fnoWrapper, namedNode(expandPrefix("rr:predicateObjectMap")), mnemonicIsNullPomap);
    this.store.addQuad(mnemonicIsNullPomap, namedNode(expandPrefix("rr:predicate")), namedNode(expandPrefix("grel:bool_b")));
    const mnemonicIsNullOmap = blankNode();
    this.store.addQuad(mnemonicIsNullPomap, namedNode(expandPrefix("rr:objectMap")), mnemonicIsNullOmap);
    const nestedFnoLogic = blankNode();
    this.store.addQuad(mnemonicIsNullOmap, namedNode(expandPrefix("fnml:functionValue")), nestedFnoLogic);
    const mnemonicIsNullNestedDefPomap = blankNode();
    this.store.addQuad(nestedFnoLogic, namedNode(expandPrefix("rr:predicateObjectMap")), mnemonicIsNullNestedDefPomap);
    this.store.addQuad(mnemonicIsNullNestedDefPomap, namedNode(expandPrefix("rr:predicate")), namedNode(expandPrefix("fno:executes")));
    const mnemonicIsNullNestedDefOmap = blankNode();
    this.store.addQuad(mnemonicIsNullNestedDefPomap, namedNode(expandPrefix("rr:objectMap")), mnemonicIsNullNestedDefOmap);
    this.store.addQuad(mnemonicIsNullNestedDefOmap, namedNode(expandPrefix("rr:constant")), namedNode(expandPrefix("idlab-fn:isNull")));
    const mnemonicIsNullNestedArgPomap = blankNode();
    this.store.addQuad(nestedFnoLogic, namedNode(expandPrefix("rr:predicateObjectMap")), mnemonicIsNullNestedArgPomap);
    this.store.addQuad(mnemonicIsNullNestedArgPomap, namedNode(expandPrefix("rr:predicate")), namedNode(expandPrefix("idlab-fn:str")));
    const mnemonicIsNullNestedArgOmap = blankNode();
    this.store.addQuad(mnemonicIsNullNestedArgPomap, namedNode(expandPrefix("rr:objectMap")), mnemonicIsNullNestedArgOmap);
    for (const [predicate, object] of inputTuples) {
        this.store.addQuad(mnemonicIsNullNestedArgOmap, predicate, object);
    }
    const mnemonicUriMaskPomap = blankNode();
    this.store.addQuad(fnoWrapper, namedNode(expandPrefix("rr:predicateObjectMap")), mnemonicUriMaskPomap);
    this.store.addQuad(mnemonicUriMaskPomap, namedNode(expandPrefix("rr:predicate")), namedNode(expandPrefix("grel:any_false")));
    const mnemonicUriMaskOmap = blankNode();
    this.store.addQuad(mnemonicUriMaskPomap, namedNode(expandPrefix("rr:objectMap")), mnemonicUriMaskOmap);
    this.store.addQuad(mnemonicUriMaskOmap, returnPredicate, returnObject);
  }
  public serialize(): Promise<string> {
    for (const tm of this.triplesMaps) {
      const tmNode = this._createNode(tm.id);
      this.store.addQuad(tmNode, namedNode(expandPrefix("rdf:type")), namedNode(expandPrefix("rr:TriplesMap")));
      const lsNode = blankNode();
      this.store.addQuad(tmNode, namedNode(expandPrefix("rml:logicalSource")), lsNode);
      this.store.addQuad(lsNode, namedNode(expandPrefix("rml:source")), literal(tm.logicalSource.source));
      this.store.addQuad(lsNode, namedNode(expandPrefix("rml:referenceFormulation")), namedNode(expandPrefix("ql:CSV")));
      const smNode = blankNode();
      this.store.addQuad(tmNode, namedNode(expandPrefix("rr:subjectMap")), smNode);
      tm.subjectMap.class.forEach(c => this.store.addQuad(smNode, namedNode(expandPrefix("rr:class")), this._createNode(c)));
      if (tm.subjectMap.mnemonic) {
        const inputTuples: [Term, Term][] = [[namedNode(expandPrefix("rml:reference")), literal(tm.subjectMap.mnemonic)]];
        let template = tm.subjectMap.template ? tm.subjectMap.template.replace(/{UUID[^}]*}/g, `urn:uuid:${tm.uuid}`) : undefined;
        const returnPredicate = template ? namedNode(expandPrefix("rr:template")) : namedNode(expandPrefix("rr:constant"));
        const returnObject = template ? literal(template) : this._createNode(tm.subjectMap.constant!);
        this._addFnoMapValueUnlessIsNull(smNode, [returnPredicate, returnObject], inputTuples);
      } else {
        if (tm.subjectMap.template) {
          let template = tm.subjectMap.template.replace(/{UUID[^}]*}/g, `urn:uuid:${tm.uuid}`);
          this.store.addQuad(smNode, namedNode(expandPrefix("rr:template")), literal(template));
        }
        if (tm.subjectMap.constant) this.store.addQuad(smNode, namedNode(expandPrefix("rr:constant")), this._createNode(tm.subjectMap.constant));
      }
      if (tm.subjectMap.termType) this.store.addQuad(smNode, namedNode(expandPrefix("rr:termType")), namedNode(expandPrefix("rr:" + tm.subjectMap.termType)));
      for (const pom of tm.predicateObjectMaps) {
        const pomNode = blankNode();
        this.store.addQuad(tmNode, namedNode(expandPrefix("rr:predicateObjectMap")), pomNode);
        this.store.addQuad(pomNode, namedNode(expandPrefix("rr:predicate")), this._createNode(pom.predicate));
        const omNode = blankNode();
        this.store.addQuad(pomNode, namedNode(expandPrefix("rr:objectMap")), omNode);

        if (pom.objectMap.parentTriplesMap) {
          this.store.addQuad(omNode, namedNode(expandPrefix("rr:parentTriplesMap")), this._createNode(pom.objectMap.parentTriplesMap));
        } else if (pom.objectMap.reference) {
          const privateMnemonics = ['ARCHAU', 'CMTAU'];
          if (privateMnemonics.includes(pom.objectMap.reference)) {
            this.store.addQuad(omNode, namedNode(expandPrefix("rr:constant")), this._createNode(`censored#${pom.objectMap.reference}`));
          } else {
            this.store.addQuad(omNode, namedNode(expandPrefix("rml:reference")), literal(pom.objectMap.reference));
          }
        } else if (pom.objectMap.template) {
          let template = pom.objectMap.template.replace(/{UUID[^}]*}/g, `urn:uuid:${tm.uuid}`);
          this.store.addQuad(omNode, namedNode(expandPrefix("rr:template")), literal(template));
        } else if (pom.objectMap.constant) {
          const term = pom.objectMap.termType === "Literal" ? literal(pom.objectMap.constant, pom.objectMap.language) : this._createNode(pom.objectMap.constant);
          this.store.addQuad(omNode, namedNode(expandPrefix("rr:constant")), term);
        }
        if (pom.objectMap.termType) this.store.addQuad(omNode, namedNode(expandPrefix("rr:termType")), namedNode(expandPrefix("rr:" + pom.objectMap.termType)));
      }
    }
    return new Promise((resolve, reject) => {
      this.writer.addQuads(this.store.getQuads(null, null, null, null));
      this.writer.end((error, result) => {
        if (error) reject(error);
        else resolve(result);
      });
    });
  }
}
