import { useApiQuery } from "@/api/queries";
import { Badge } from "@/components/Badge/Badge";
import { IconButton } from "@/components/IconButton/IconButton";
import { Panel } from "@/components/Panel/Panel";
import { StatusPanel } from "@/components/StatusPanel/StatusPanel";
import { dateTimeIn } from "@/lib/format";
import { useAccountTimezone } from "@/lib/useAccountTimezone";

import { STATUS_DISPLAY, whenOf } from "../rules";

import styles from "./CampaignReportView.module.css";

const BACK_LABEL = "Back to campaigns";
const CLICKS_LABEL = "Clicks";
const CLICKS_NOTE = "Clicks are counted nightly.";
const COUNTS = [
  { key: "recipients", label: "Recipients" },
  { key: "sent", label: "Sent" },
  { key: "refused", label: "Refused" },
  { key: "delivered", label: "Delivered" },
  { key: "undelivered", label: "Undelivered" },
] as const;

interface Props {
  campaignId: string;
  onClose: () => void;
}

export function CampaignReportView({ campaignId, onClose }: Props) {
  const report = useApiQuery("get", "/api/app/campaigns/{campaignId}/report", {
    params: { path: { campaignId: campaignId } },
  });
  const timezone = useAccountTimezone();
  const back = <IconButton icon="back" label={BACK_LABEL} onClick={onClose} />;

  if (report.data === undefined) {
    return <StatusPanel />;
  }
  if (report.data.status === "ERROR") {
    return (
      <Panel>
        {back}
        <p className={styles.error} role="alert">
          {report.data.message}
        </p>
      </Panel>
    );
  }

  const { campaign, clicks } = report.data.data;
  const status = STATUS_DISPLAY[campaign.status];
  const actions = (
    <div className={styles.actions}>
      <Badge tone={status.tone}>{status.label}</Badge>
      {back}
    </div>
  );

  return (
    <Panel actions={actions} title={campaign.name}>
      <p className={styles.when}>{dateTimeIn(whenOf(campaign), timezone, "medium")}</p>
      <dl className={styles.tiles}>
        {COUNTS.map((count) => (
          <div className={styles.tile} key={count.key}>
            <dt className={styles.term}>{count.label}</dt>
            <dd className={styles.value}>{campaign.counts[count.key]}</dd>
          </div>
        ))}
        <div className={styles.tile}>
          <dt className={styles.term}>{CLICKS_LABEL}</dt>
          <dd className={styles.value}>{clicks}</dd>
        </div>
      </dl>
      <p className={styles.note}>{CLICKS_NOTE}</p>
    </Panel>
  );
}
