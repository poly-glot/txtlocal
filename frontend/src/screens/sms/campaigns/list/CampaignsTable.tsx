import { useState } from "react";

import type { Campaign, SendersView } from "@/api/generated/dashboard";
import { Badge } from "@/components/Badge/Badge";
import { Table } from "@/components/Table/Table";
import type { Column, Sort } from "@/components/Table/Table";
import { sortRows, toggleSort } from "@/components/Table/sort";
import { dateTimeIn } from "@/lib/format";

import { senderDisplayOf } from "../../rules";
import { STATUS_DISPLAY, whenOf } from "../rules";
import { CampaignRowActions } from "./CampaignRowActions";

import styles from "./CampaignsTable.module.css";

const CAMPAIGN_HEADER = "CAMPAIGN";
const COUNT_PAD = 6;
const DATE_HEADER = "DATE";
const EMPTY_MSG = "No results";
const FROM_HEADER = "FROM";
const RECIPIENTS_HEADER = "RECIPIENTS";
const SORT_BY_DATE: Sort = { direction: "desc", key: "date" };
const STATUS_HEADER = "STATUS";

interface Props {
  onCancel: (campaign: Campaign) => void;
  onDuplicate: (campaign: Campaign) => void;
  onOpen: (campaign: Campaign) => void;
  rows: readonly Campaign[];
  senders: SendersView;
  timezone: string | undefined;
}

export function CampaignsTable(props: Props) {
  const [sort, setSort] = useState(SORT_BY_DATE);

  return (
    <Table
      columns={columnsFor(props)}
      emptyText={EMPTY_MSG}
      keyOf={(row) => row.campaignId}
      onSort={(key) => {
        setSort(toggleSort(sort, key));
      }}
      rows={sortRows(props.rows, sort, valueFor(props))}
      sort={sort}
    />
  );
}

function columnsFor(props: Props): readonly Column<Campaign>[] {
  return [
    { header: CAMPAIGN_HEADER, key: "campaign", render: (row) => row.name },
    {
      header: STATUS_HEADER,
      key: "status",
      render: (row) => (
        <Badge tone={STATUS_DISPLAY[row.status].tone}>{STATUS_DISPLAY[row.status].label}</Badge>
      ),
    },
    {
      header: DATE_HEADER,
      key: "date",
      render: (row) => dateTimeIn(whenOf(row), props.timezone, "medium"),
    },
    {
      header: FROM_HEADER,
      key: "from",
      render: (row) => senderDisplayOf(props.senders, row.senderId),
    },
    {
      header: RECIPIENTS_HEADER,
      key: "recipients",
      render: (row) => (
        <span className={styles.recipients}>
          {row.counts.recipients}
          <CampaignRowActions
            campaign={row}
            onCancel={props.onCancel}
            onDuplicate={props.onDuplicate}
            onOpen={props.onOpen}
          />
        </span>
      ),
    },
  ];
}

function valueFor(props: Props) {
  return (row: Campaign, key: string): string => {
    if (key === "date") {
      return whenOf(row);
    }
    if (key === "from") {
      return senderDisplayOf(props.senders, row.senderId);
    }
    if (key === "recipients") {
      return String(row.counts.recipients).padStart(COUNT_PAD, "0");
    }
    if (key === "status") {
      return STATUS_DISPLAY[row.status].label;
    }

    return row.name;
  };
}
