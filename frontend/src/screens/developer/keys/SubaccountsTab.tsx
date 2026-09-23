import { keepPreviousData } from "@tanstack/react-query";
import { useState } from "react";

import type { UserRow } from "@/api/generated/dashboard";
import { useApiQuery } from "@/api/queries";
import { Panel } from "@/components/Panel/Panel";
import { StatusPanel } from "@/components/StatusPanel/StatusPanel";
import type { Sort } from "@/components/Table/Table";
import { toggleSort } from "@/components/Table/sort";

import { AddSubaccountModal } from "./AddSubaccountModal";
import { ApiKeyModal } from "./ApiKeyModal";
import { RegenerateKeyModal } from "./RegenerateKeyModal";
import { SubaccountsTable } from "./SubaccountsTable";
import { SubaccountsToolbar } from "./SubaccountsToolbar";

const TITLE = "Subaccounts";

export function SubaccountsTab() {
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<Sort>({ direction: "asc", key: "username" });
  const [adding, setAdding] = useState(false);
  const [regenerating, setRegenerating] = useState<UserRow>();
  const [revealedKey, setRevealedKey] = useState<string>();
  const users = useApiQuery(
    "get",
    "/api/app/account/users",
    { params: { query: { q: q } } },
    { placeholderData: keepPreviousData },
  );

  if (users.data === undefined) {
    return <StatusPanel title={TITLE} />;
  }
  if (users.data.status === "ERROR") {
    return <StatusPanel error={users.data.message} title={TITLE} />;
  }

  const toolbar = (
    <SubaccountsToolbar
      onAdd={() => {
        setAdding(true);
      }}
      onSearch={setQ}
    />
  );

  return (
    <Panel actions={toolbar} title={TITLE}>
      <SubaccountsTable
        onRegenerate={setRegenerating}
        onSort={(key) => {
          setSort(toggleSort(sort, key));
        }}
        rows={users.data.data}
        sort={sort}
      />
      {adding ? (
        <AddSubaccountModal
          onClose={() => {
            setAdding(false);
          }}
          onCreated={(created) => {
            setAdding(false);
            setRevealedKey(created.apiKey);
          }}
        />
      ) : null}
      {regenerating === undefined ? null : (
        <RegenerateKeyModal
          onClose={() => {
            setRegenerating(undefined);
          }}
          onRegenerated={(apiKey) => {
            setRegenerating(undefined);
            setRevealedKey(apiKey);
          }}
          user={regenerating}
        />
      )}
      {revealedKey === undefined ? null : (
        <ApiKeyModal
          apiKey={revealedKey}
          onDone={() => {
            setRevealedKey(undefined);
          }}
        />
      )}
    </Panel>
  );
}
