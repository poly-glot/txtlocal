import styles from "./PhoneNumber.module.css";

interface Props {
  e164: string;
}

export function PhoneNumber({ e164 }: Props) {
  return (
    <span className={styles.number} dir="ltr">
      {e164}
    </span>
  );
}
