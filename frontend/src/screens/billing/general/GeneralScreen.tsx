import { useApiQuery } from "@/api/queries";
import { Panel } from "@/components/Panel/Panel";
import { StatusPanel } from "@/components/StatusPanel/StatusPanel";

import { GeneralForm } from "./GeneralForm";

const TITLE = "General";

export function GeneralScreen() {
  const general = useApiQuery("get", "/api/app/billing/general");

  if (general.data === undefined) {
    return <StatusPanel title={TITLE} />;
  }
  if (general.data.status === "ERROR") {
    return <StatusPanel error={general.data.message} title={TITLE} />;
  }

  return (
    <Panel title={TITLE}>
      <GeneralForm initial={general.data.data} />
    </Panel>
  );
}
