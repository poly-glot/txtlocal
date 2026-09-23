import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

const matchNoMedia = (media: string) => ({ matches: false, media });

Object.defineProperty(window, "matchMedia", { value: matchNoMedia, writable: true });

afterEach(cleanup);
