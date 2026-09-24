import { Icon } from "@/components/Icon/Icon";

import styles from "./Brand.module.css";

const BRAND = "txtlocal";

export function Brand() {
  return (
    <a className={styles.brand} href="#top">
      <span className={styles.tile}>
        <Icon name="brand" />
      </span>
      <span className={styles.name}>{BRAND}</span>
    </a>
  );
}
