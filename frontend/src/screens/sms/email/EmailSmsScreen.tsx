import { Panel } from "@/components/Panel/Panel";

import { AllowedAddressesSection } from "./AllowedAddressesSection";
import { EmailSmsFaq } from "./EmailSmsFaq";
import { EmailSmsSteps } from "./EmailSmsSteps";

import styles from "./EmailSmsScreen.module.css";

const COMING_SOON_NOTE = "Email to SMS is coming soon";
const FAQ_HEADING = "Frequently asked questions";
const HEADING = "Email SMS";

export function EmailSmsScreen() {
  return (
    <div className={styles.page}>
      <Panel title={HEADING}>
        <p className={styles.comingSoon}>{COMING_SOON_NOTE}</p>
        <EmailSmsSteps />
      </Panel>
      <Panel title={FAQ_HEADING}>
        <EmailSmsFaq />
      </Panel>
      <AllowedAddressesSection />
    </div>
  );
}
