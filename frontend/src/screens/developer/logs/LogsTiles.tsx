import type { LogTiles } from "@/api/generated/dashboard";

import styles from "./LogsTiles.module.css";

const FAILED_LABEL = "Failed";
const SUCCESSFUL_LABEL = "Successful";
const TOTAL_LABEL = "Total requests";

interface Props {
  tiles: LogTiles;
}

interface StatProps {
  count: number;
  label: string;
}

export function LogsTiles({ tiles }: Props) {
  return (
    <div className={styles.tiles}>
      <Stat count={tiles.total} label={TOTAL_LABEL} />
      <Stat count={tiles.successful} label={SUCCESSFUL_LABEL} />
      <Stat count={tiles.failed} label={FAILED_LABEL} />
    </div>
  );
}

function Stat({ count, label }: StatProps) {
  return (
    <p className={styles.stat}>
      <span className={styles.value}>{count}</span> <span className={styles.label}>{label}</span>
    </p>
  );
}
