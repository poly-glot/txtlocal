import { PhonePreview } from "@/components/PhonePreview/PhonePreview";

import styles from "./EmailSmsSteps.module.css";

const BODY_LABEL = "Body";
const ILLUSTRATION_BODY = "Please give me a call on 0400000000 Regards, Jan";
const ILLUSTRATION_SUBJECT = "Re: Sales Report";
const ILLUSTRATION_TO = "1234567890@sms.<domain>, 0987654321@sms.<domain>";
const SUBJECT_LABEL = "Subject";
const TO_LABEL = "To";

const STEPS = [
  "Enter your contact's mobile number followed by @sms.<domain>",
  "Enter the message in the subject or body of the email.",
  "Message is sent from your Email Inbox, straight to their mobile.",
] as const;

export function EmailSmsSteps() {
  return (
    <div className={styles.layout}>
      <ol className={styles.steps}>
        {STEPS.map((step, index) => (
          <li className={styles.step} key={step}>
            <span className={styles.number}>{index + 1}</span>
            <p className={styles.text}>{step}</p>
          </li>
        ))}
      </ol>
      <div className={styles.illustration}>
        <div className={styles.envelope}>
          <p className={styles.field}>
            {TO_LABEL}: <span className={styles.value}>{ILLUSTRATION_TO}</span>
          </p>
          <p className={styles.field}>
            {SUBJECT_LABEL}: <span className={styles.value}>{ILLUSTRATION_SUBJECT}</span>
          </p>
          <p className={styles.field}>
            {BODY_LABEL}: <span className={styles.value}>{ILLUSTRATION_BODY}</span>
          </p>
        </div>
        <PhonePreview body={`${ILLUSTRATION_SUBJECT} ${ILLUSTRATION_BODY}`} title="" />
      </div>
    </div>
  );
}
