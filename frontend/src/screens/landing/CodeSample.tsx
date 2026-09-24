import styles from "./CodeSample.module.css";

const FILE_NAME = "send-sms.sh";
const SAMPLE_LABEL = "Sending an SMS with curl";
const SAMPLE = `curl https://txtlocal.junaid.guru/api/v3/sms/send \\
  -u "you@example.com:$TXTLOCAL_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"messages": [{"to": "+447400123123",
        "body": "Your table is ready"}]}'`;

export function CodeSample() {
  return (
    <figure aria-label={SAMPLE_LABEL} className={styles.window}>
      <div className={styles.bar}>
        <span className={styles.dots} />
        <span className={styles.file}>{FILE_NAME}</span>
      </div>
      <pre className={styles.code}>{SAMPLE}</pre>
    </figure>
  );
}
