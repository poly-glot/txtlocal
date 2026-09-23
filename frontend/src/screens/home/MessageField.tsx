import { Money } from "@/components/Money/Money";
import { segmentSummary, segmentsOf } from "@/rules/segments";

import { counterText } from "./rules";

import styles from "./MessageField.module.css";

const BODY_PLACEHOLDER = "Type a test message to check out how it works.";
const LABEL = "Message content";

interface Props {
  balanceMicro: number;
  body: string;
  onChange: (body: string) => void;
}

export function MessageField({ balanceMicro, body, onChange }: Props) {
  const segments = segmentsOf(body);
  const summary = segmentSummary(segments);

  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor="test-body">
        {LABEL}
      </label>
      <textarea
        aria-describedby="test-body-summary"
        className={styles.textarea}
        id="test-body"
        onChange={(event) => {
          onChange(event.target.value);
        }}
        placeholder={BODY_PLACEHOLDER}
        required
        value={body}
      />
      <div className={styles.footer}>
        <span className={styles.credit}>
          <Money micro={balanceMicro} /> credit
        </span>
        <span className={styles.counter} title={summary}>
          {counterText(segments)}
        </span>
      </div>
      <p hidden id="test-body-summary">
        {summary}
      </p>
    </div>
  );
}
