import styles from "./StatusMessage.module.css";

const LOADING_MSG = "Loading…";

interface Props {
  error?: string | undefined;
}

export function StatusMessage({ error }: Props) {
  if (error === undefined) {
    return <p className={styles.status}>{LOADING_MSG}</p>;
  }

  return (
    <p className={styles.error} role="alert">
      {error}
    </p>
  );
}
