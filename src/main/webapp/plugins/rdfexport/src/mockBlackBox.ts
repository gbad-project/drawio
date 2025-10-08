const BLACK_BOX_PREFIX = "[BLACKBOX]";
const BLACK_BOX_SUFFIX = "[/BLACKBOX]";
export function runMockBlackBox(serializedXml: string): string {
  const lengthLabel = serializedXml.length.toString(10);
  return `${BLACK_BOX_PREFIX} len=${lengthLabel}\n${serializedXml}\n${BLACK_BOX_SUFFIX}`;
}
