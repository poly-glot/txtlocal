import type { ScreenProduct } from "../../rules";

export function addFirstLabel(product: ScreenProduct): string {
  return `CLICK HERE TO ADD YOUR FIRST ${product} CAMPAIGN`;
}

export function campaignsHeading(product: ScreenProduct): string {
  return `${product} Campaigns`;
}
