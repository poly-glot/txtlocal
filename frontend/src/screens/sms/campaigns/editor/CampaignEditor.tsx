import type { Campaign } from "@/api/generated/dashboard";
import { useApiQuery } from "@/api/queries";
import { StatusPanel } from "@/components/StatusPanel/StatusPanel";
import type { Result } from "@/types";

import type { ScreenProduct } from "../../rules";
import { CampaignForm } from "./CampaignForm";

interface Props {
  campaignId: string | undefined;
  onClose: () => void;
  product: ScreenProduct;
}

export function CampaignEditor({ campaignId, onClose, product }: Props) {
  const campaign = useApiQuery(
    "get",
    "/api/app/campaigns/{campaignId}",
    { params: { path: { campaignId: campaignId ?? "" } } },
    { enabled: campaignId !== undefined },
  );
  const senders = useApiQuery("get", "/api/app/senders");
  const opening = campaignId !== undefined && campaign.data === undefined;

  if (opening || senders.data === undefined) {
    return <StatusPanel />;
  }
  if (campaign.data?.status === "ERROR") {
    return <StatusPanel error={campaign.data.message} />;
  }
  if (senders.data.status === "ERROR") {
    return <StatusPanel error={senders.data.message} />;
  }

  return (
    <CampaignForm
      campaign={loadedOf(campaign.data)}
      onClose={onClose}
      product={product}
      senders={senders.data.data}
    />
  );
}

function loadedOf(result: Result<Campaign> | undefined): Campaign | undefined {
  return result?.status === "OK" ? result.data : undefined;
}
