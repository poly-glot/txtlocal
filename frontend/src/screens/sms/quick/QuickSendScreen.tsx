import { useApiQuery } from "@/api/queries";
import { Panel } from "@/components/Panel/Panel";
import { StatusPanel } from "@/components/StatusPanel/StatusPanel";
import { useAccountTimezone } from "@/lib/useAccountTimezone";

import type { ScreenProduct } from "../rules";
import { QuickComposer } from "./QuickComposer";
import { QuickMmsForm } from "./QuickMmsForm";
import { QuickSmsForm } from "./QuickSmsForm";

const FORMS = { MMS: QuickMmsForm, SMS: QuickSmsForm };

const titleOf = (kind: ScreenProduct) => `Quick ${kind}`;

interface Props {
  kind: ScreenProduct;
}

export function QuickSendScreen({ kind }: Props) {
  const senders = useApiQuery("get", "/api/app/senders");
  const timezone = useAccountTimezone();
  const title = titleOf(kind);

  if (senders.data === undefined) {
    return <StatusPanel title={title} />;
  }
  if (senders.data.status === "ERROR") {
    return <StatusPanel error={senders.data.message} title={title} />;
  }

  return (
    <Panel title={title}>
      <QuickComposer Form={FORMS[kind]} kind={kind} timezone={timezone} view={senders.data.data} />
    </Panel>
  );
}
