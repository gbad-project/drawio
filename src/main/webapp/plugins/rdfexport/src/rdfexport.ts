import { DOMParser } from "@xmldom/xmldom";
import { DataFactory, Writer } from "n3";
import type {
  DrawIOXMLTree as IDrawIOXMLTree,
  Individual,
  Arrow,
  Blocks,
  SerialisationConfig,
  Cell,
  Dimensions,
  ArrowData,
} from "./types";
import { JSDOM } from "jsdom";

const { namedNode, literal, quad } = DataFactory;

const rico = (p: string) => `https://www.ica.org/standards/RiC/ontology#${p}`;

const BASE_URI = "https://example.com";
const get_prefixes = () => ({
  rico: "https://www.ica.org/standards/RiC/ontology#",
  add: `${BASE_URI}/Schema/Description-Listings/`,
  auth: `${BASE_URI}/Schema/Authority/`,
  owl: "http://www.w3.org/2002/07/owl#",
  rdfs: "http://www.w3.org/2000/01/rdf-schema#",
  rr: "http://www.w3.org/ns/r2rml#",
  rml: "http://semweb.mmlab.be/ns/rml#",
});

class DrawIOXMLTree implements IDrawIOXMLTree {
  doc: Document;
  draw_io_xml_tree: Element;
  literal_node_html_parser: any; // Simplified for now
  individual_cells: [Cell, Individual, Dimensions][] = [];
  arrow_cells: ArrowData[] = [];
  literal_cells: [Cell, Dimensions][] = [];
  raw_xml: string;
  prefixes: Record<string, string>;
  root: Element;
  cells: Element[];

  constructor(raw_xml: string, prefixes: Record<string, string>) {
    this.raw_xml = raw_xml;
    this.prefixes = prefixes;
    this.doc = new DOMParser().parseFromString(raw_xml, "application/xml");
    this.draw_io_xml_tree = this.doc.documentElement;
    const root = this.draw_io_xml_tree.getElementsByTagName("root")[0];
    if (!root) {
      throw new Error("Could not find root element in draw.io XML");
    }
    this.root = root;
    this.cells = Array.from(this.root.getElementsByTagName("mxCell"));
    this._extract_individual_and_arrow_and_literal_cells();
  }

  private _extract_individual_and_arrow_and_literal_cells(): void {
    for (const cell of this.cells) {
      const value = this._value_of(cell);
      if (!value) {
        this._add_arrow_if_find_label(cell);
        continue;
      }

      const valuePrefix = value.split(":")[0];
      if (!this.prefixes[valuePrefix]) {
        if (this._is_possible_literal(cell)) {
          this.literal_cells.push([cell, this._dimensions(cell)]);
        }
        continue;
      }

      const parent = this._parent_of(cell);
      if (!parent) continue;

      const individual_identifier = this._value_of(parent);
      if (!individual_identifier) continue;

      const prefix = value.split(":")[0];
      const ric_class_local = value.split(":")[1];
      if (prefix && ric_class_local) {
        const ric_class = `${prefix}:${ric_class_local.trim()}`;
        const individual: Individual = {
          identifier: individual_identifier,
          ric_class: ric_class,
        };
        this.individual_cells.push([
          cell,
          individual,
          this._dimensions(parent),
        ]);
      }
    }
  }

  private _value_of(cell: Element): string {
    const value = cell.getAttribute("value");
    if (!value) return "";
    const dom = new JSDOM(`<!DOCTYPE html><body>${value}</body>`);
    return dom.window.document.body.textContent?.trim() || "";
  }

  private _cell_with_id(id: string): Element | null {
    return this.cells.find((c) => c.getAttribute("id") === id) || null;
  }

  private _parent_of(cell: Element): Element | null {
    const parentId = cell.getAttribute("parent");
    if (!parentId) return null;
    return this._cell_with_id(parentId);
  }

  private _dimensions(cell: Element): Dimensions {
    const geo = cell.getElementsByTagName("mxGeometry")[0];
    if (!geo) return [0, 0, 0, 0];
    const x = parseFloat(geo.getAttribute("x") || "0");
    const y = parseFloat(geo.getAttribute("y") || "0");
    const width = parseFloat(geo.getAttribute("width") || "0");
    const height = parseFloat(geo.getAttribute("height") || "0");
    return [x, y, width, height];
  }

  private _is_possible_literal(cell: Element): boolean {
    const parentId = cell.getAttribute("parent");
    if (parentId !== "1") return false;
    const style = cell.getAttribute("style");
    return style?.includes("rounded=1") || false;
  }

  private _children_of(parentId: string): Element[] {
    return this.cells.filter((c) => c.getAttribute("parent") === parentId);
  }

  private _arrow_label(arrow_cell: Element): string {
    const children = this._children_of(arrow_cell.getAttribute("id") || "");
    for (const cell of children) {
      const style = cell.getAttribute("style");
      if (style && style.includes("edgeLabel")) {
        return this._value_of(cell);
      }
    }
    return "";
  }

  private _add_arrow_if_find_label(cell: Element): void {
    const label = this._arrow_label(cell);
    if (label) {
      this.arrow_cells.push([cell, null, null, label]);
    }
  }

  public individuals_and_arrows(): (Individual | Arrow)[] {
    const result: (Individual | Arrow)[] = [];
    for (const [, individual] of this.individual_cells) {
      result.push(individual);
    }

    for (const [arrow_cell, , , label] of this.arrow_cells) {
      const sourceId = arrow_cell.getAttribute("source");
      const targetId = arrow_cell.getAttribute("target");

      if (sourceId && targetId) {
        const sourceCell = this._cell_with_id(sourceId);
        const targetCell = this._cell_with_id(targetId);

        if (sourceCell && targetCell) {
          const source = this._source_or_target(sourceCell, true);
          const target = this._source_or_target(targetCell, false);

          if (source && target) {
            result.push({
              identifier: label,
              source,
              target,
            });
          }
        }
      }
    }
    return result;
  }

  private _source_or_target(
    cell: Element,
    must_be_individual: boolean
  ): string {
    let value = this._value_of(cell);
    const prefix = value.split(":")[0];
    if (this.prefixes[prefix]) {
      const parent = this._parent_of(cell);
      if (parent) {
        return this._value_of(parent);
      }
    }
    return value;
  }
}

function individual_blocks(
  individuals_and_arrows: (Individual | Arrow)[]
): Blocks {
  const blocks: Blocks = {};

  for (const item of individuals_and_arrows) {
    if ("ric_class" in item) {
      // It's an Individual
      const individual = item as Individual;
      if (!blocks[individual.identifier]) {
        blocks[individual.identifier] = {};
      }
      if (!blocks[individual.identifier]["Types"]) {
        blocks[individual.identifier]["Types"] = new Set();
      }
      blocks[individual.identifier]["Types"].add(individual.ric_class);
    } else {
      // It's an Arrow
      const arrow = item as Arrow;
      if (!blocks[arrow.source]) {
        blocks[arrow.source] = {};
      }
      if (!blocks[arrow.source][arrow.identifier]) {
        blocks[arrow.source][arrow.identifier] = new Set();
      }
      blocks[arrow.source][arrow.identifier].add(arrow.target);
    }
  }
  return blocks;
}

export function createRml(xml: string): string {
  const prefixes = get_prefixes();
  const drawIOXMLTree = new DrawIOXMLTree(xml, prefixes);
  const individualsAndArrows = drawIOXMLTree.individuals_and_arrows();
  const blocks = individual_blocks(individualsAndArrows);

  // At this point, `blocks` contains a representation of the graph.
  // The next step is to use this to generate the RML.
  // For now, I'll just return a JSON representation of the blocks for debugging.

  return JSON.stringify(
    Object.fromEntries(
      Object.entries(blocks).map(([k, v]) => [
        k,
        Object.fromEntries(
          Object.entries(v).map(([prop, values]) => [prop, Array.from(values)])
        ),
      ])
    ),
    null,
    2
  );
}
