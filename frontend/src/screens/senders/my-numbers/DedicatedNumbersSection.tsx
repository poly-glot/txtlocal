import { Link } from "react-router";

import type { SenderView } from "@/api/generated/dashboard";

import { NumbersSection } from "../NumbersSection";
import { DedicatedNumbersTable } from "./DedicatedNumbersTable";

import styles from "./DedicatedNumbersSection.module.css";

const BUY_PATH = "/senders/buy";
const COPY = "Purchase a dedicated phone number that is used by your business only.";
const PURCHASE_LABEL = "+ Purchase";

interface Props {
  onCancel: (sender: SenderView) => void;
  rows: readonly SenderView[];
}

export function DedicatedNumbersSection({ onCancel, rows }: Props) {
  return (
    <NumbersSection
      action={
        <Link className={styles.purchase} data-variant="primary" to={BUY_PATH}>
          {PURCHASE_LABEL}
        </Link>
      }
      copy={COPY}
      title="Dedicated Numbers"
    >
      <DedicatedNumbersTable onCancel={onCancel} rows={rows} />
    </NumbersSection>
  );
}
