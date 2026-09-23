import { useApiQuery } from "@/api/queries";
import { Panel } from "@/components/Panel/Panel";
import { StatusPanel } from "@/components/StatusPanel/StatusPanel";

import { MessagingSettingsForm } from "./MessagingSettingsForm";

const TITLE = "General";

export function MessagingGeneralTab() {
  const settings = useApiQuery("get", "/api/app/account/settings/messaging");

  if (settings.data === undefined) {
    return <StatusPanel title={TITLE} />;
  }
  if (settings.data.status === "ERROR") {
    return <StatusPanel error={settings.data.message} title={TITLE} />;
  }

  return (
    <Panel title={TITLE}>
      <MessagingSettingsForm initial={settings.data.data} />
    </Panel>
  );
}
