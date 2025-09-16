export type Cell = Element;
export type CellID = string;
export type XCoordinate = number;
export type YCoordinate = number;
export type Width = number;
export type Height = number;
export type ArrowStart = [XCoordinate, YCoordinate] | null;
export type ArrowEnd = [XCoordinate, YCoordinate] | null;
export type Label = string;
export type ArrowData = [Cell, ArrowStart, ArrowEnd, Label];
export type Dimensions = [XCoordinate, YCoordinate, Width, Height];
export type Paragraph = string;
export type Metacharacter = string;
export type Replacement = string;

export interface Individual {
  identifier: string;
  ric_class: string;
}

export interface Arrow {
  identifier: string;
  source: string;
  target: string;
}

export interface DrawIOXMLTree {
  doc: Document;
  draw_io_xml_tree: Element;
  literal_node_html_parser: any; // Simplified for now
  individual_cells: [Cell, Individual, Dimensions][];
  arrow_cells: ArrowData[];
  literal_cells: [Cell, Dimensions][];
  raw_xml: string;
  prefixes: Record<string, string>;
}

export type Blocks = Record<string, Record<string, Set<string>>>;

export interface SerialisationConfig {
  infer_type_of_literals: boolean;
  include_preamble: boolean;
  ontology_iri: string | null;
  prefix: string | null;
  prefix_iri: string | null;
  indentation: number;
  include_label: boolean;
}
