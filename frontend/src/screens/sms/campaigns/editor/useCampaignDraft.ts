import { useState } from "react";

import type { Campaign, CampaignDraft, CampaignQuote } from "@/api/generated/dashboard";
import { useApiMutation } from "@/api/queries";
import type { Result } from "@/types";

import type { ScreenProduct } from "../../rules";
import { draftOf } from "./rules";

export function useCampaignDraft(campaign: Campaign | undefined, product: ScreenProduct) {
  const [draft, setDraft] = useState(() => draftOf(campaign, product));
  const [dirty, setDirty] = useState(false);
  const [quoted, setQuoted] = useState<CampaignQuote>();
  const [savedId, setSavedId] = useState(campaign?.campaignId);
  const create = useApiMutation("post", "/api/app/campaigns");
  const update = useApiMutation("put", "/api/app/campaigns/{campaignId}");
  const quote = useApiMutation("post", "/api/app/campaigns/{campaignId}/quote");
  const remove = useApiMutation("delete", "/api/app/campaigns/{campaignId}");

  const persist = (): Promise<Result<Campaign>> =>
    savedId === undefined
      ? create.mutateAsync({ body: draft })
      : update.mutateAsync({ body: draft, params: { path: { campaignId: savedId } } });

  const save = async (): Promise<Result<string>> => {
    const saved = await persist();
    if (saved.status === "ERROR") {
      return saved;
    }
    setDirty(false);
    setSavedId(saved.data.campaignId);

    return { data: saved.data.campaignId, status: "OK" };
  };

  const next = async (): Promise<Result<CampaignQuote>> => {
    const saved = await save();
    if (saved.status === "ERROR") {
      return saved;
    }

    const priced = await quote.mutateAsync({ params: { path: { campaignId: saved.data } } });
    if (priced.status === "OK") {
      setQuoted(priced.data);
    }

    return priced;
  };

  const discard = () => {
    if (campaign === undefined && savedId !== undefined) {
      remove.mutate({ params: { path: { campaignId: savedId } } });
    }
  };

  const patch = (change: Partial<CampaignDraft>) => {
    setDraft({ ...draft, ...change });
    setDirty(true);
    setQuoted(undefined);
  };

  return { discard, dirty, draft, next, patch, quoted, save, savedId };
}
