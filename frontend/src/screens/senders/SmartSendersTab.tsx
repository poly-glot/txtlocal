import { useState } from "react";
import type { ChangeEvent } from "react";
import { Link } from "react-router";

import type { SendersView } from "@/api/generated/dashboard";
import { useApiMutation } from "@/api/queries";
import { Select } from "@/components/Select/Select";
import { Table } from "@/components/Table/Table";
import type { Column } from "@/components/Table/Table";
import { Toast } from "@/components/Toast/Toast";
import type { Notice } from "@/types";

import { countryLabel, enabledCountriesOf, senderOptionsFor } from "./rules";

import styles from "./SmartSendersTab.module.css";

const ACCOUNT_SETTINGS_PATH = "/account";
const COPY =
  "We've automatically set the safest and best senders for each country — that's why they're called Smart Senders. You can update them if needed. We'll only show senders that are compliant for each location. You can use Smart Senders in our SMS products.";
const EMPTY_MSG = "No countries are enabled for sending yet.";
const ENABLE_MORE = "Enable more countries via Global Sending";
const LEARN_MORE = "Learn about Smart Senders";
const SELECT_LABEL = "Smart Sender";
const USE_FOR = "SMS";

type Choose = (country: string) => (event: ChangeEvent<HTMLSelectElement>) => void;

interface Props {
  view: SendersView;
}

export function SmartSendersTab({ view }: Props) {
  const [notice, setNotice] = useState<Notice>();
  const save = useApiMutation("put", "/api/app/senders/smart/{country}");

  const choose: Choose = (country) => (event) => {
    save.mutate(
      { body: { senderId: event.target.value }, params: { path: { country } } },
      {
        onSuccess: (result) => {
          if (result.status === "ERROR") {
            setNotice({ message: result.message, tone: "error" });
          }
        },
      },
    );
  };

  return (
    <section className={styles.tab}>
      <p className={styles.copy}>{COPY}</p>
      <p className={styles.links}>
        <span className={styles.learn}>{LEARN_MORE}</span>
        <Link to={ACCOUNT_SETTINGS_PATH}>{ENABLE_MORE}</Link>
      </p>
      <Table
        columns={columnsFor(choose, view)}
        emptyText={EMPTY_MSG}
        keyOf={(country) => country}
        rows={enabledCountriesOf(view)}
      />
      <Toast
        notice={notice}
        onDismiss={() => {
          setNotice(undefined);
        }}
      />
    </section>
  );
}

function columnsFor(choose: Choose, view: SendersView): readonly Column<string>[] {
  return [
    { header: "Sending to", key: "country", render: (country) => countryLabel(country) },
    {
      header: SELECT_LABEL,
      key: "sender",
      render: (country) => (
        <Select
          id={`smart-sender-${country}`}
          label={SELECT_LABEL}
          labelHidden
          onChange={choose(country)}
          options={senderOptionsFor(view, country)}
          value={view.smart[country] ?? ""}
        />
      ),
    },
    { header: "Use for", key: "useFor", render: () => USE_FOR },
  ];
}
