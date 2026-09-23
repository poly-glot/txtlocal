import { describe, expect, it } from "vitest";

import { fakeFetch, refusal } from "@/test/fakeFetch";

import { uploadedMediaKey } from "./media";

const UPLOAD_URL = "/api/app/messaging/media/media-1";

const picture = () => new File([new Uint8Array(10)], "pic.png", { type: "image/png" });

describe("uploadedMediaKey", () => {
  it("mints a key and puts the file where it points", async () => {
    const fetcher = fakeFetch({
      "POST /api/app/messaging/media": { key: "media-1", uploadUrl: UPLOAD_URL },
      [`PUT ${UPLOAD_URL}`]: new Response(null, { status: 204 }),
    });

    const key = await uploadedMediaKey(picture(), fetcher);

    expect(key).toBe("media-1");
    expect(fetcher.calls.map((call) => `${call.method} ${call.path}`)).toEqual([
      "POST /api/app/messaging/media",
      `PUT ${UPLOAD_URL}`,
    ]);
  });

  it("reports no key and puts nothing when the mint is refused", async () => {
    const fetcher = fakeFetch({
      "POST /api/app/messaging/media": refusal(400, "Unsupported media type"),
    });

    const key = await uploadedMediaKey(picture(), fetcher);

    expect(key).toBeUndefined();
    expect(fetcher.calls.map((call) => call.method)).toEqual(["POST"]);
  });

  it("reports no key when the file does not arrive", async () => {
    const fetcher = fakeFetch({
      "POST /api/app/messaging/media": { key: "media-1", uploadUrl: UPLOAD_URL },
      [`PUT ${UPLOAD_URL}`]: new Response(null, { status: 500 }),
    });

    expect(await uploadedMediaKey(picture(), fetcher)).toBeUndefined();
  });
});
