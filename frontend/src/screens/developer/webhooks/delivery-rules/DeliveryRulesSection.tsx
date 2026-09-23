import { useApiQuery } from "@/api/queries";
import { StatusPanel } from "@/components/StatusPanel/StatusPanel";

import { DeliveryRulesPanel } from "./DeliveryRulesPanel";

const HEADING = "Delivery Report Rules";

export function DeliveryRulesSection() {
  const rules = useApiQuery("get", "/api/app/rules/delivery");

  if (rules.data === undefined) {
    return <StatusPanel title={HEADING} />;
  }
  if (rules.data.status === "ERROR") {
    return <StatusPanel error={rules.data.message} title={HEADING} />;
  }

  return <DeliveryRulesPanel rules={rules.data.data} title={HEADING} />;
}
