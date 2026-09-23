import type { Fetch } from "@/types";

import { callApi, useFetcher } from "./client";

export function useMediaUpload(): (file: File) => Promise<string | undefined> {
  const fetcher = useFetcher();

  return (file) => uploadedMediaKey(file, fetcher);
}

export async function uploadedMediaKey(file: File, fetcher: Fetch): Promise<string | undefined> {
  const minted = await callApi(fetcher, "post", "/api/app/messaging/media", {
    body: { contentType: file.type },
  });
  if (minted.status === "ERROR") {
    return undefined;
  }

  const put = await fetcher(minted.data.uploadUrl, {
    body: file,
    headers: { "content-type": file.type },
    method: "PUT",
  });

  return put.ok ? minted.data.key : undefined;
}
