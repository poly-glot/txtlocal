import { useState } from "react";

import type { Campaign } from "@/api/generated/dashboard";
import { useApiMutation } from "@/api/queries";
import { refusalNotice } from "@/lib/notice";
import type { Notice, Result } from "@/types";

export function useCampaignRowActions() {
  const [notice, setNotice] = useState<Notice>();
  const cancelMutation = useApiMutation("post", "/api/app/campaigns/{campaignId}/cancel");
  const duplicateMutation = useApiMutation("post", "/api/app/campaigns/{campaignId}/duplicate");

  const refused = (result: Result<Campaign>) => {
    if (result.status === "ERROR") {
      setNotice(refusalNotice(result));
    }
  };

  return {
    cancel: (campaign: Campaign) => {
      cancelMutation.mutate(
        { params: { path: { campaignId: campaign.campaignId } } },
        { onSuccess: refused },
      );
    },
    dismiss: () => {
      setNotice(undefined);
    },
    duplicate: (campaign: Campaign) => {
      duplicateMutation.mutate(
        { params: { path: { campaignId: campaign.campaignId } } },
        { onSuccess: refused },
      );
    },
    notice,
  };
}
