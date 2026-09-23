import { useApiQuery } from "@/api/queries";
import { Panel } from "@/components/Panel/Panel";
import { StatusPanel } from "@/components/StatusPanel/StatusPanel";

import { ProfileForm } from "./ProfileForm";

const TITLE = "Your Details";

export function ProfileScreen() {
  const me = useApiQuery("get", "/api/app/me");

  if (me.data === undefined) {
    return <StatusPanel title={TITLE} />;
  }
  if (me.data.status === "ERROR") {
    return <StatusPanel error={me.data.message} title={TITLE} />;
  }

  return (
    <Panel title={TITLE}>
      <ProfileForm me={me.data.data} />
    </Panel>
  );
}
