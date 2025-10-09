declare module "*.py?raw" {
  const content: string;
  export default content;
}

declare module "*.whl?arraybuffer" {
  const content: ArrayBuffer;
  export default content;
}

declare module "*.whl.base64?raw" {
  const content: string;
  export default content;
}
