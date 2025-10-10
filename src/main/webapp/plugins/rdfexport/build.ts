import type { BunPlugin } from "bun";
import { resolve, dirname } from "path";

const rawPlugin: BunPlugin = {
  name: "raw-loader",
  setup(build) {
    build.onResolve({ filter: /\?raw$/ }, (args) => {
      const pathWithoutQuery = args.path.replace(/\?raw$/, "");
      const resolvedPath = resolve(dirname(args.importer), pathWithoutQuery);

      return {
        path: resolvedPath,
        namespace: "raw-loader",
      };
    });

    build.onLoad({ filter: /.*/, namespace: "raw-loader" }, async (args) => {
      const file = Bun.file(args.path);
      const contents = await file.text();

      return {
        contents: `export default ${JSON.stringify(contents)}`,
        loader: "js",
      };
    });
  },
};

await Bun.build({
  entrypoints: ["./src/rdfexport.ts"],
  outdir: "./dist",
  plugins: [rawPlugin],
});
