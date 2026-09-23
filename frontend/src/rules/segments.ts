const GSM_BASIC =
  "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà";
const GSM_EXTENSION = "\f^{}\\[~]|€";
export const GSM_PART = 153;
export const GSM_SINGLE = 160;
export const UCS2_PART = 67;
const UCS2_SINGLE = 70;

const gsmBasic = new Set(GSM_BASIC);
const gsmExtension = new Set(GSM_EXTENSION);

export const MAX_PARTS = 8;

export type Encoding = "GSM-7" | "UCS-2";

export interface Segments {
  encoding: Encoding;
  length: number;
  parts: number;
}

export function segmentsOf(body: string): Segments {
  let septets = 0;
  for (const char of body) {
    const cost = septetsOf(char);
    if (cost === null) {
      return ucs2(body);
    }
    septets += cost;
  }

  return { encoding: "GSM-7", length: septets, parts: partsOf(septets, GSM_SINGLE, GSM_PART) };
}

export function segmentSummary(segments: Segments): string {
  return `Approx. ${String(segments.length)} characters/${String(segments.parts)} SMS per recipient.`;
}

function septetsOf(char: string): number | null {
  if (gsmBasic.has(char)) {
    return 1;
  }
  if (gsmExtension.has(char)) {
    return 2;
  }

  return null;
}

function ucs2(body: string): Segments {
  const units = body.length;

  return { encoding: "UCS-2", length: units, parts: partsOf(units, UCS2_SINGLE, UCS2_PART) };
}

function partsOf(length: number, single: number, part: number): number {
  return length <= single ? 1 : Math.ceil(length / part);
}
