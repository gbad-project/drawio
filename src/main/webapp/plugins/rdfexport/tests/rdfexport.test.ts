import { test, expect } from "bun:test";
import { createHash } from "crypto";
import { fileURLToPath } from "url";
import { DOMParser } from "@xmldom/xmldom";
import { readFileSync, readdirSync, existsSync } from "fs";
import { join, extname, basename } from "path";

const rdfexportUrl = fileURLToPath(
  new URL("../src/rdfexport.ts", import.meta.url),
);
const fixturesDir = fileURLToPath(new URL("./fixtures", import.meta.url));

const pluginCallbacks: Array<(ui: any) => void> = [];

(globalThis as any).mxConstants = {
  NODETYPE_ELEMENT: 1,
  NODETYPE_TEXT: 3,
  NODETYPE_CDATA: 4,
  NODETYPE_COMMENT: 8,
  NODETYPE_DOCUMENT: 9,
  NODETYPE_DOCUMENT_FRAGMENT: 11,
};

// Add this line
const mxConstants = (globalThis as any).mxConstants;

const mxUtils = {
  createXmlDocument(): Document {
    const parser = new DOMParser();
    const doc = parser.parseFromString("<root />", "application/xml");
    const root = doc.documentElement;
    if (root) {
      doc.removeChild(root);
    }
    return doc;
  },
  getPrettyXml(
    node: Node | null,
    tab?: string,
    indent?: string,
    newline?: string,
    ns?: string,
  ): string {
    const result: string[] = [];

    if (node != null) {
      const actualTab = tab ?? "  ";
      const actualIndent = indent ?? "";
      const actualNewline = newline ?? "\n";

      const element = node as Element;
      const namespace = element.namespaceURI;
      if (namespace != null && namespace !== ns) {
        ns = namespace;
      }

      switch (node.nodeType) {
        case mxConstants.NODETYPE_DOCUMENT:
          result.push(
            mxUtils.getPrettyXml(
              (node as Document).documentElement,
              actualTab,
              actualIndent,
              actualNewline,
              ns,
            ),
          );
          break;
        case mxConstants.NODETYPE_DOCUMENT_FRAGMENT: {
          let child: ChildNode | null = (node as DocumentFragment).firstChild;
          while (child != null) {
            result.push(
              mxUtils.getPrettyXml(
                child,
                actualTab,
                actualIndent,
                actualNewline,
                ns,
              ),
            );
            child = child.nextSibling;
          }
          break;
        }
        case mxConstants.NODETYPE_COMMENT: {
          const value = mxUtils.getTextContent(node);
          if (value.length > 0) {
            result.push(`${actualIndent}<!--${value}-->${actualNewline}`);
          }
          break;
        }
        case mxConstants.NODETYPE_TEXT: {
          const value = mxUtils.trim(mxUtils.getTextContent(node));
          if (value.length > 0) {
            result.push(
              `${actualIndent}${mxUtils.htmlEntities(value, false, false)}${actualNewline}`,
            );
          }
          break;
        }
        case mxConstants.NODETYPE_CDATA: {
          const value = mxUtils.getTextContent(node);
          if (value.length > 0) {
            result.push(`${actualIndent}<![CDATA[${value}]]${actualNewline}`);
          }
          break;
        }
        default: {
          result.push(`${actualIndent}<${element.nodeName}`);

          const attrs = element.attributes;
          if (attrs != null) {
            for (let i = 0; i < attrs.length; i += 1) {
              const attr = attrs.item(i);
              if (attr != null) {
                const value = mxUtils.htmlEntities(attr.nodeValue ?? "");
                result.push(` ${attr.nodeName}="${value}"`);
              }
            }
          }

          let child: ChildNode | null = element.firstChild;
          if (child != null) {
            result.push(`>${actualNewline}`);
            while (child != null) {
              result.push(
                mxUtils.getPrettyXml(
                  child,
                  actualTab,
                  actualIndent + actualTab,
                  actualNewline,
                  ns,
                ),
              );
              child = child.nextSibling;
            }
            result.push(
              `${actualIndent}</${element.nodeName}>${actualNewline}`,
            );
          } else {
            result.push(` />${actualNewline}`);
          }
          break;
        }
      }
    }

    return result.join("");
  },
  getTextContent(node: Node): string {
    return node.textContent ?? "";
  },
  ltrim(value: string, chars?: string): string {
    const pattern = chars ?? "\\s|\\0";
    return value != null
      ? value.replace(new RegExp(`^[${pattern}]+`, "g"), "")
      : "";
  },
  rtrim(value: string, chars?: string): string {
    const pattern = chars ?? "\\s|\\0";
    return value != null
      ? value.replace(new RegExp(`[${pattern}]+$`, "g"), "")
      : "";
  },
  trim(value: string, chars?: string): string {
    return mxUtils.ltrim(mxUtils.rtrim(value, chars), chars);
  },
  htmlEntities(
    value: string,
    newline: boolean | null = true,
    quotes: boolean | null = true,
    tab: boolean | null = true,
  ): string {
    let result = String(value ?? "");
    result = result.replace(/&/g, "&amp;");
    result = result.replace(/</g, "&lt;");
    result = result.replace(/>/g, "&gt;");

    if (quotes == null || quotes) {
      result = result.replace(/"/g, "&quot;");
      result = result.replace(/'/g, "&#39;");
    }

    if (newline == null || newline) {
      result = result.replace(/\n/g, "&#xa;");
    }

    if (tab == null || tab) {
      result = result.replace(/\t/g, "&#x9;");
    }

    return result;
  },
};

(globalThis as any).mxUtils = mxUtils;
(globalThis as any).mxResources = { parse: () => {} };
(globalThis as any).Draw = {
  loadPlugin(callback: (ui: any) => void) {
    pluginCallbacks.push(callback);
  },
};

function runRdfExportTest(fixtureFile: string, sampleFile: string) {
  test(`${fixtureFile}: rdfexport plugin exports RDF with expected checksum`, async () => {
    if (pluginCallbacks.length === 0) {
      await import(rdfexportUrl);
    }

    const fixturePath = join(fixturesDir, fixtureFile);
    const xml = await Bun.file(fixturePath).text();

    const parser = new DOMParser();
    const xmlDoc = parser.parseFromString(xml, "application/xml");
    const graphModel = xmlDoc.getElementsByTagName("mxGraphModel").item(0);
    const diagramElement = xmlDoc.getElementsByTagName("diagram").item(0);

    if (!graphModel) {
      throw new Error("Failed to locate mxGraphModel element in fixture");
    }

    if (!diagramElement) {
      throw new Error("Failed to locate diagram element in fixture");
    }

    const pageId = diagramElement.getAttribute("id") ?? "diagram";
    const baseFilename = fixtureFile.replace(/\.drawio$/, "");

    const actions: Record<string, () => void> = {};
    const savedExports: Array<{
      filename: string;
      format: string;
      data: string;
      mimeType: string;
    }> = [];
    const exportMenuItems: string[][] = [];
    const menuStub: any = { funct: () => {} };

    const editorUi = {
      editor: {
        getGraphXml: () => graphModel,
      },
      currentPage: {
        getId: () => pageId,
      },
      actions: {
        addAction(name: string, fn: () => void) {
          actions[name] = fn;
        },
      },
      menus: {
        get(name: string) {
          if (name === "exportAs") {
            return menuStub;
          }
          return null;
        },
        addMenuItems(menu: any, items: string[], parent: any) {
          exportMenuItems.push(items);
        },
      },
      getBaseFilename() {
        return baseFilename;
      },
      saveData(
        filename: string,
        format: string,
        data: string,
        mimeType: string,
      ) {
        savedExports.push({ filename, format, data, mimeType });
      },
      handleError(err: Error) {
        throw err;
      },
    };

    for (const callback of pluginCallbacks) {
      callback(editorUi);
    }

    menuStub.funct([], null);

    expect(actions.exportRdfXml).toBeDefined();

    if (!actions.exportRdfXml) {
      throw new Error("exportRdfXml action was not registered by the plugin");
    }
    actions.exportRdfXml();

    expect(savedExports).toHaveLength(1);
    const exportData = savedExports[0]!;
    const { filename, format, data, mimeType } = exportData;

    expect(filename).toBe(`${baseFilename}.rdf`);
    expect(format).toBe("rdf");
    expect(mimeType).toBe("application/rdf+xml");
    expect(exportMenuItems).toContainEqual(["-", "exportRdfXml"]);

    const md5 = createHash("md5").update(data).digest("hex");
    const refMd5 = createHash("md5")
      .update(readFileSync(join(fixturesDir, sampleFile)))
      .digest("hex");
    expect(md5).toBe(refMd5);
  });
}

for (const file of readdirSync(fixturesDir)) {
  if (extname(file) === ".drawio") {
    const base = basename(file, ".drawio");
    const rdfFile = base + ".rdf";

    if (!existsSync(join(fixturesDir, rdfFile))) {
      test.skip(`${file}: skipped (no matching ${rdfFile})`, () => {});
      continue;
    }

    runRdfExportTest(file, rdfFile);
  }
}
