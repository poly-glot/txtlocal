import styles from "./CodeSample.module.css";

const FILE_NAME = "send-sms.sh";
const SAMPLE_LABEL = "Sending an SMS with curl";
const LINES = [
  [
    ["command", "curl"],
    ["plain", " https://txtlocal.junaid.guru/api/v3/sms/send \\"],
  ],
  [
    ["flag", "  -u"],
    ["string", ' "you@example.com:$TXTLOCAL_API_KEY"'],
    ["plain", " \\"],
  ],
  [
    ["flag", "  -H"],
    ["string", ' "Content-Type: application/json"'],
    ["plain", " \\"],
  ],
  [
    ["flag", "  -d"],
    ["string", ' \'{"messages": [{"to": "+447400123123",'],
  ],
  [["string", '        "body": "Your table is ready"}]}\'']],
] as const;

export function CodeSample() {
  return (
    <figure aria-label={SAMPLE_LABEL} className={styles.window}>
      <div className={styles.bar}>
        <span className={styles.dots} />
        <span className={styles.file}>{FILE_NAME}</span>
      </div>
      <pre className={styles.code}>
        {LINES.map((line, index) => (
          <span className={styles.line} key={index}>
            {line.map(([kind, text]) => (
              <span className={styles.token} data-kind={kind} key={text}>
                {text}
              </span>
            ))}
          </span>
        ))}
      </pre>
    </figure>
  );
}
