import { keepPreviousData } from "@tanstack/react-query";
import { useState } from "react";

import type { Campaign, SendersView } from "@/api/generated/dashboard";
import { useApiQuery } from "@/api/queries";
import { Icon } from "@/components/Icon/Icon";
import { IconButton } from "@/components/IconButton/IconButton";
import { Input } from "@/components/Input/Input";
import { Panel } from "@/components/Panel/Panel";
import { StatusPanel } from "@/components/StatusPanel/StatusPanel";
import { Toast } from "@/components/Toast/Toast";
import { dataOf } from "@/lib/format";
import { useAccountTimezone } from "@/lib/useAccountTimezone";

import type { ScreenProduct } from "../../rules";
import { CampaignsTable } from "./CampaignsTable";
import { addFirstLabel, campaignsHeading } from "./rules";
import { useCampaignRowActions } from "./useCampaignRowActions";

import styles from "./CampaignList.module.css";

const ADD_LABEL = "Add campaign";
const ENTRIES_NOTE = "Show 20 Entries";
const NO_SENDERS: SendersView = { senders: {}, smart: {} };
const SEARCH_LABEL = "Search";
const SEARCH_PLACEHOLDER = "Search...";

interface Props {
  onCreate: () => void;
  onOpen: (campaign: Campaign) => void;
  product: ScreenProduct;
}

export function CampaignList({ onCreate, onOpen, product }: Props) {
  const [q, setQ] = useState("");
  const campaigns = useApiQuery(
    "get",
    "/api/app/campaigns",
    { params: { query: { kind: product, q } } },
    { placeholderData: keepPreviousData },
  );
  const rowActions = useCampaignRowActions();
  const senders = useApiQuery("get", "/api/app/senders");
  const timezone = useAccountTimezone();
  const title = campaignsHeading(product);
  const add = <IconButton icon="plus" label={ADD_LABEL} onClick={onCreate} variant="primary" />;

  if (campaigns.data === undefined) {
    return <StatusPanel title={title} />;
  }
  if (campaigns.data.status === "ERROR") {
    return <StatusPanel error={campaigns.data.message} title={title} />;
  }
  if (campaigns.data.data.items.length === 0 && q === "") {
    return (
      <Panel actions={add} title={title}>
        <button className={styles.empty} onClick={onCreate} type="button">
          <Icon name="document" size={20} />
          {addFirstLabel(product)}
        </button>
      </Panel>
    );
  }

  return (
    <Panel actions={add} title={title}>
      <div className={styles.body}>
        <Input
          id="campaign-search"
          label={SEARCH_LABEL}
          onChange={(event) => {
            setQ(event.target.value);
          }}
          placeholder={SEARCH_PLACEHOLDER}
          type="search"
          value={q}
        />
        <Toast notice={rowActions.notice} onDismiss={rowActions.dismiss} />
        <CampaignsTable
          onCancel={rowActions.cancel}
          onDuplicate={rowActions.duplicate}
          onOpen={onOpen}
          rows={campaigns.data.data.items}
          senders={dataOf(senders.data, NO_SENDERS)}
          timezone={timezone}
        />
        <p className={styles.note}>{ENTRIES_NOTE}</p>
      </div>
    </Panel>
  );
}
