import { useState } from "react";

import type { Campaign } from "@/api/generated/dashboard";

import type { ScreenProduct } from "../rules";
import { CampaignEditor } from "./editor/CampaignEditor";
import { CampaignList } from "./list/CampaignList";
import { CampaignReportView } from "./report/CampaignReportView";

type View =
  | { campaignId: string | undefined; kind: "EDITOR" }
  | { campaignId: string; kind: "REPORT" }
  | { kind: "LIST" };

const LIST_VIEW: View = { kind: "LIST" };
const NEW_CAMPAIGN_VIEW: View = { campaignId: undefined, kind: "EDITOR" };

interface Props {
  product: ScreenProduct;
}

export function CampaignsScreen({ product }: Props) {
  const [view, setView] = useState(LIST_VIEW);

  const close = () => {
    setView(LIST_VIEW);
  };

  if (view.kind === "EDITOR") {
    return <CampaignEditor campaignId={view.campaignId} onClose={close} product={product} />;
  }
  if (view.kind === "REPORT") {
    return <CampaignReportView campaignId={view.campaignId} onClose={close} />;
  }

  return (
    <CampaignList
      onCreate={() => {
        setView(NEW_CAMPAIGN_VIEW);
      }}
      onOpen={(campaign) => {
        setView(viewOf(campaign));
      }}
      product={product}
    />
  );
}

function viewOf(campaign: Campaign): View {
  return campaign.status === "DRAFT"
    ? { campaignId: campaign.campaignId, kind: "EDITOR" }
    : { campaignId: campaign.campaignId, kind: "REPORT" };
}
