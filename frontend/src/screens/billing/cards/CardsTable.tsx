import type { CardView } from "@/api/generated/dashboard";
import { Badge } from "@/components/Badge/Badge";
import { Button } from "@/components/Button/Button";
import { Table } from "@/components/Table/Table";
import type { Column } from "@/components/Table/Table";

import { cardExpiry } from "./rules";

import styles from "./CardsTable.module.css";

const DEFAULT_BADGE = "Default";
const EMPTY_MSG = "No card";
const MAKE_DEFAULT_LABEL = "Make default";
const REMOVE_LABEL = "Remove";

const cardName = (card: CardView) => `${card.brand} •••• ${card.last4}`;
const makeDefaultName = (card: CardView) => `Make default: ${cardName(card)}`;
const removeName = (card: CardView) => `Remove card: ${cardName(card)}`;

interface Props {
  onRemove: (paymentMethodId: string) => void;
  onSetDefault: (paymentMethodId: string) => void;
  rows: readonly CardView[];
}

export function CardsTable({ onRemove, onSetDefault, rows }: Props) {
  return (
    <Table
      columns={columnsFor(onRemove, onSetDefault)}
      emptyText={EMPTY_MSG}
      keyOf={(row) => row.paymentMethodId}
      rows={rows}
    />
  );
}

function columnsFor(
  onRemove: (paymentMethodId: string) => void,
  onSetDefault: (paymentMethodId: string) => void,
): readonly Column<CardView>[] {
  return [
    {
      header: "CREDIT CARD",
      key: "brand",
      render: (row) => (
        <span className={styles.card}>
          <span className={styles.number}>{cardName(row)}</span>
          {row.isDefault ? <Badge tone="accent">{DEFAULT_BADGE}</Badge> : null}
        </span>
      ),
    },
    {
      header: "CARDHOLDER NAME",
      key: "cardholderName",
      render: (row) => <span className={styles.cell}>{row.cardholderName}</span>,
    },
    {
      header: "EXP. DATE",
      key: "expiry",
      render: (row) => <span className={styles.cell}>{cardExpiry(row.expMonth, row.expYear)}</span>,
    },
    {
      align: "end",
      header: "ACTIONS",
      key: "actions",
      render: (row) => (
        <span className={styles.actions}>
          {row.isDefault ? null : (
            <Button
              aria-label={makeDefaultName(row)}
              onClick={() => {
                onSetDefault(row.paymentMethodId);
              }}
              variant="tonal"
            >
              {MAKE_DEFAULT_LABEL}
            </Button>
          )}
          <Button
            aria-label={removeName(row)}
            onClick={() => {
              onRemove(row.paymentMethodId);
            }}
            variant="danger"
          >
            {REMOVE_LABEL}
          </Button>
        </span>
      ),
    },
  ];
}
