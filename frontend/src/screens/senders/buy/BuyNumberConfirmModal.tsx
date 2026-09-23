import { useState } from "react";

import type { CatalogueNumber } from "@/api/generated/dashboard";
import { useApiMutation } from "@/api/queries";
import { Button } from "@/components/Button/Button";
import { Modal } from "@/components/Modal/Modal";
import { Money } from "@/components/Money/Money";
import { Toast } from "@/components/Toast/Toast";
import type { Notice } from "@/types";

import styles from "./BuyNumberConfirmModal.module.css";

const BUY_LABEL = "Buy";
const CANCEL_LABEL = "Cancel";
const CONFIRM_SUFFIX =
  "a month, charged now and every month from your balance. Auto recharge will be turned on.";
const TITLE_ID = "buy-number-title";

interface Props {
  number: CatalogueNumber;
  onBought: () => void;
  onClose: () => void;
}

export function BuyNumberConfirmModal({ number, onBought, onClose }: Props) {
  const [notice, setNotice] = useState<Notice>();
  const buy = useApiMutation("post", "/api/app/numbers/{number}/buy");

  const confirm = () => {
    buy.mutate(
      { params: { path: { number: number.value } } },
      {
        onSuccess: (result) => {
          if (result.status === "ERROR") {
            setNotice({ message: result.message, tone: "error" });
            return;
          }
          onBought();
        },
      },
    );
  };

  return (
    <Modal labelledBy={TITLE_ID} onClose={onClose}>
      <Modal.Header>
        <Modal.Title id={TITLE_ID}>Rent {number.value}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <p className={styles.copy}>
          Rent {number.value} for <Money micro={number.monthlyPriceMicro} /> {CONFIRM_SUFFIX}
        </p>
        <Toast
          notice={notice}
          onDismiss={() => {
            setNotice(undefined);
          }}
        />
      </Modal.Body>
      <Modal.Footer>
        <Button onClick={onClose} variant="secondary">
          {CANCEL_LABEL}
        </Button>
        <Button disabled={buy.isPending} onClick={confirm}>
          {BUY_LABEL}
        </Button>
      </Modal.Footer>
    </Modal>
  );
}
