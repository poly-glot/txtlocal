import styles from "./EnabledMark.module.css";

const ENABLED_LABEL = "Enabled";

interface Props {
  enabled: boolean;
}

export function EnabledMark({ enabled }: Props) {
  if (!enabled) {
    return null;
  }

  return (
    <span aria-label={ENABLED_LABEL} className={styles.mark}>
      ✓
    </span>
  );
}
