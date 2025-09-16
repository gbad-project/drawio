import { JSDOM } from 'jsdom';
import { DataFactory, Writer, Store, Quad, NamedNode, Literal, BlankNode, Term } from 'n3';

const { namedNode, literal, quad, blankNode } = DataFactory;

// --- NAMESPACES and PREFIXES ---
const prefixes: { [key: string]: string } = {
    '': 'https://data.archives.gov.on.test.gbad.ca/Schema/Mapping#',
    'add': 'https://data.archives.gov.on.test.gbad.ca/Schema/Description-Listings/',
    'auth': 'https://data.archives.gov.on.test.gbad.ca/Schema/Authority/',
    'owl': 'http://www.w3.org/2002/07/owl#',
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
    'rr': 'http://www.w3.org/ns/r2rml#',
    'rml': 'http://semweb.mmlab.be/ns/rml#',
    'ql': 'http://semweb.mmlab.be/ns/ql#',
    'fnml': 'http://semweb.mmlab.be/ns/fnml#',
    'fno': 'https://w3id.org/function/ontology#',
    'idlab-fn': 'https://w3id.org/imec/idlab/function#',
    'grel': 'http://users.ugent.be/~bjdmeest/function/grel.ttl#',
    'rico': 'https://www.ica.org/standards/RiC/ontology#',
};

function expandPrefix(prefixedName: string): string {
    const parts = prefixedName.split(':', 2);
    if (parts.length > 1 && prefixes[parts[0]]) {
        return prefixes[parts[0]] + parts[1];
    }
    return prefixedName;
}

// --- INTERFACES for RML Structure ---
interface LogicalSource {
    source: string;
    referenceFormulation: 'CSV';
    iterator?: string;
}

interface SubjectMap {
    class: string[];
    template?: string;
    constant?: string;
    termType?: 'IRI' | 'BlankNode';
}

interface ObjectMap {
    reference?: string;
    template?: string;
    constant?: string;
    parentTriplesMap?: string;
    termType?: 'IRI' | 'Literal' | 'BlankNode';
}

interface PredicateObjectMap {
    predicate: string[];
    objectMap: ObjectMap;
}

interface TriplesMap {
    id: string;
    logicalSource: LogicalSource;
    subjectMap: SubjectMap;
    predicateObjectMaps: PredicateObjectMap[];
}

// --- RML Generator Main Class ---
export async function createRml(drawioXml: string, sourceFilename: string): Promise<string> {
    const parser = new DrawioParser(drawioXml, sourceFilename);
    const triplesMaps = parser.parse();
    const serializer = new RmlSerializer(triplesMaps);
    return serializer.serialize();
}


// --- Drawio XML Parser ---
class DrawioParser {
    private dom: JSDOM;
    private cells: { [id: string]: Element } = {};
    private individuals: { [id: string]: { cell: Element, name: string, classSpecifierIds: string[] } } = {};
    private classSpecifiers: { [id: string]: { cell: Element, name: string } } = {};
    private literals: { [id: string]: { cell: Element, name: string } } = {};
    private edges: Element[] = [];

    constructor(private xmlString: string, private sourceFilename: string) {
        this.dom = new JSDOM(xmlString, { contentType: 'application/xml' });
        const cellElements = Array.from(this.dom.window.document.querySelectorAll('mxCell'));

        for (const cell of cellElements) {
            const id = cell.getAttribute('id');
            if (!id || id === '0' || id === '1') continue;
            this.cells[id] = cell;
            if (cell.hasAttribute('edge')) {
                this.edges.push(cell);
            }
        }
    }

    private getCleanValue(cell: Element): string {
        const value = cell.getAttribute('value') || '';
        const tempDom = new JSDOM(`<body>${value}</body>`);
        let text = tempDom.window.document.body.textContent || '';
        text = text.replace(/<br\s*\/?>/gi, '\n');
        return text.replace(/\s+/g, ' ').trim();
    }

    private classifyCells(): void {
        const individualCandidates: { [id: string]: { cell: Element, name: string, classSpecifierIds: string[] } } = {};

        // First pass: identify all cells and potential individuals/literals
        for (const id in this.cells) {
            const cell = this.cells[id];
            const style = cell.getAttribute('style') || '';
            const value = this.getCleanValue(cell);

            if (style.includes('swimlane') || (!cell.hasAttribute('edge') && cell.getAttribute('parent') === '1')) {
                individualCandidates[id] = { cell, name: value, classSpecifierIds: [] };
            } else if (style.includes('rounded=1') || style.includes('shape=note')) {
                this.literals[id] = { cell, name: value };
            }
        }

        // Second pass: associate class specifiers with individuals
        for (const id in this.cells) {
            const cell = this.cells[id];
            const value = this.getCleanValue(cell);
            const parentId = cell.getAttribute('parent');

            if (value.includes(':') && !value.startsWith('http') && parentId && individualCandidates[parentId]) {
                const classNames = value.split(' ').filter(v => v.includes(':'));
                if (classNames.length > 0) {
                    this.classSpecifiers[id] = { cell, name: value };
                    individualCandidates[parentId].classSpecifierIds.push(id);
                }
            }
        }

        this.individuals = individualCandidates;
    }

    public parse(): TriplesMap[] {
        this.classifyCells();
        const triplesMaps: { [id: string]: TriplesMap } = {};

        // Create TriplesMaps for each individual
        for (const id in this.individuals) {
            const individual = this.individuals[id];
            const classes = individual.classSpecifierIds.flatMap(csId => this.classSpecifiers[csId].name.split(' ')).filter(v => v.includes(':'));

            if (classes.length === 0) continue;

            const subjectMap: SubjectMap = { class: classes, termType: 'IRI' };
            const individualName = individual.name;

            if (individualName.startsWith('rr:template=')) {
                subjectMap.template = individualName.substring('rr:template='.length);
            } else if (individualName.startsWith('rr:constant=')) {
                subjectMap.constant = individualName.substring('rr:constant='.length);
            } else if (individualName) {
                if (!individualName.includes(':') && !individualName.includes('{')) {
                    subjectMap.template = `{${individualName}}`;
                }
            }

            triplesMaps[id] = {
                id,
                logicalSource: {
                    source: this.sourceFilename,
                    referenceFormulation: 'CSV',
                },
                subjectMap,
                predicateObjectMaps: [],
            };
        }

        // Process edges
        for (const edge of this.edges) {
            const sourceId = edge.getAttribute('source');
            const targetId = edge.getAttribute('target');
            let label = this.getCleanValue(edge);
            if (!label) {
                // Try to find label in child cells for complex edges
                const childCells = Array.from(edge.getElementsByTagName('mxCell'));
                for(const child of childCells) {
                    if (child.getAttribute('style')?.includes('edgeLabel')) {
                        label = this.getCleanValue(child);
                        break;
                    }
                }
            }


            if (!sourceId || !targetId || !label) continue;

            const sourceMap = triplesMaps[sourceId];
            if (!sourceMap) continue;

            let objectMap: ObjectMap = {};
            if (triplesMaps[targetId]) {
                objectMap.parentTriplesMap = targetId;
            } else if (this.literals[targetId]) {
                const literalDef = this.literals[targetId];
                const literalName = literalDef.name;
                if (literalName.startsWith('rml:reference=')) {
                    objectMap.reference = literalName.substring('rml:reference='.length);
                } else if (literalName.startsWith('rr:template=')) {
                    objectMap.template = literalName.substring('rr:template='.length);
                } else if (literalName.startsWith('rr:constant=')) {
                    objectMap.constant = literalName.substring('rr:constant='.length);
                } else {
                    objectMap.constant = literalName;
                    objectMap.termType = 'Literal';
                }
            } else {
                continue;
            }

            const predicates = label.split(',').map(p => p.trim());
            sourceMap.predicateObjectMaps.push({
                predicate: predicates,
                objectMap,
            });
        }

        return Object.values(triplesMaps);
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

    public serialize(): Promise<string> {
        for (const tm of this.triplesMaps) {
            const tmNode = namedNode(tm.id);
            this.store.addQuad(tmNode, namedNode(expandPrefix('rdf:type')), namedNode(expandPrefix('rr:TriplesMap')));

            const lsNode = blankNode();
            this.store.addQuad(tmNode, namedNode(expandPrefix('rml:logicalSource')), lsNode);
            this.store.addQuad(lsNode, namedNode(expandPrefix('rml:source')), literal(tm.logicalSource.source));
            this.store.addQuad(lsNode, namedNode(expandPrefix('rml:referenceFormulation')), namedNode(expandPrefix('ql:CSV')));
            if (tm.logicalSource.iterator) {
                this.store.addQuad(lsNode, namedNode(expandPrefix('rml:iterator')), literal(tm.logicalSource.iterator));
            }

            const smNode = blankNode();
            this.store.addQuad(tmNode, namedNode(expandPrefix('rr:subjectMap')), smNode);
            tm.subjectMap.class.forEach(c => {
                this.store.addQuad(smNode, namedNode(expandPrefix('rr:class')), namedNode(expandPrefix(c)));
            });
            if (tm.subjectMap.template) {
                this.store.addQuad(smNode, namedNode(expandPrefix('rr:template')), literal(tm.subjectMap.template));
            }
            if (tm.subjectMap.constant) {
                this.store.addQuad(smNode, namedNode(expandPrefix('rr:constant')), namedNode(expandPrefix(tm.subjectMap.constant)));
            }
            if (tm.subjectMap.termType) {
                this.store.addQuad(smNode, namedNode(expandPrefix('rr:termType')), namedNode(expandPrefix('rr:' + tm.subjectMap.termType)));
            }

            for (const pom of tm.predicateObjectMaps) {
                const pomNode = blankNode();
                this.store.addQuad(tmNode, namedNode(expandPrefix('rr:predicateObjectMap')), pomNode);
                pom.predicate.forEach(p => {
                    this.store.addQuad(pomNode, namedNode(expandPrefix('rr:predicate')), namedNode(expandPrefix(p)));
                });

                const omNode = blankNode();
                this.store.addQuad(pomNode, namedNode(expandPrefix('rr:objectMap')), omNode);

                if (pom.objectMap.parentTriplesMap) {
                    this.store.addQuad(omNode, namedNode(expandPrefix('rr:parentTriplesMap')), namedNode(pom.objectMap.parentTriplesMap));
                } else if (pom.objectMap.reference) {
                    this.store.addQuad(omNode, namedNode(expandPrefix('rml:reference')), literal(pom.objectMap.reference));
                } else if (pom.objectMap.template) {
                    this.store.addQuad(omNode, namedNode(expandPrefix('rr:template')), literal(pom.objectMap.template));
                } else if (pom.objectMap.constant) {
                    const term = pom.objectMap.termType === 'Literal' ? literal(pom.objectMap.constant) : namedNode(expandPrefix(pom.objectMap.constant));
                    this.store.addQuad(omNode, namedNode(expandPrefix('rr:constant')), term);
                }
                 if (pom.objectMap.termType) {
                    this.store.addQuad(omNode, namedNode(expandPrefix('rr:termType')), namedNode(expandPrefix('rr:' + pom.objectMap.termType)));
                }
            }
        }

        return new Promise((resolve, reject) => {
            this.writer.addQuads(this.store.getQuads(null, null, null, null));
            this.writer.end((error, result) => {
                if (error) {
                    reject(error);
                } else {
                    resolve(`@base <https://data.archives.gov.on.test.gbad.ca/> .\n${result}`);
                }
            });
        });
    }
}
