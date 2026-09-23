import { DeliveryRulesSection } from "./delivery-rules/DeliveryRulesSection";
import { InboundRulesSection } from "./inbound-rules/InboundRulesSection";

import styles from "./WebhooksScreen.module.css";

export function WebhooksScreen() {
  return (
    <div className={styles.page}>
      <InboundRulesSection />
      <DeliveryRulesSection />
    </div>
  );
}
