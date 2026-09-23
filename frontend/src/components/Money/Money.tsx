import styles from "./Money.module.css";

const MICRO_PER_POUND = 1_000_000;

type Places = 0 | 2 | 4;

interface Props {
  micro: number;
  places?: Places;
}

function formatMicro(micro: number, places: Places): string {
  const formatter = new Intl.NumberFormat("en-GB", {
    currency: "GBP",
    maximumFractionDigits: places,
    minimumFractionDigits: places,
    style: "currency",
  });

  return formatter.format(micro / MICRO_PER_POUND);
}

export function Money({ micro, places = 2 }: Props) {
  return <span className={styles.money}>{formatMicro(micro, places)}</span>;
}
