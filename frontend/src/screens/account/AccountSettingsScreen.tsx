import { useApiQuery } from "@/api/queries";
import { Panel } from "@/components/Panel/Panel";
import { StatusPanel } from "@/components/StatusPanel/StatusPanel";

import { AccountSettingsForm } from "./AccountSettingsForm";

const TITLE = "Account Details";

export function AccountSettingsScreen() {
  const settings = useApiQuery("get", "/api/app/account/settings");

  if (settings.data === undefined) {
    return <StatusPanel title={TITLE} />;
  }
  if (settings.data.status === "ERROR") {
    return <StatusPanel error={settings.data.message} title={TITLE} />;
  }

  return (
    <Panel title={TITLE}>
      <AccountSettingsForm initial={settings.data.data} />
    </Panel>
  );
}
