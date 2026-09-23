import { useState } from "react";

import type { Template } from "@/api/generated/dashboard";
import { Icon } from "@/components/Icon/Icon";
import { Input } from "@/components/Input/Input";
import type { Sort } from "@/components/Table/Table";
import { toggleSort } from "@/components/Table/sort";

import { TemplatesTable } from "./TemplatesTable";

import styles from "./TemplatesList.module.css";

const EMPTY_LINK = "Click here to add your first SMS template";
const SEARCH_LABEL = "Search";
const SEARCH_PLACEHOLDER = "Search...";

interface Props {
  onAdd: () => void;
  onDelete: (template: Template) => void;
  onEdit: (template: Template) => void;
  rows: readonly Template[];
}

export function TemplatesList({ onAdd, onDelete, onEdit, rows }: Props) {
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<Sort>({ direction: "asc", key: "name" });

  return (
    <>
      <div className={styles.search}>
        <Input
          id="template-search"
          label={SEARCH_LABEL}
          onChange={(event) => {
            setQ(event.target.value);
          }}
          placeholder={SEARCH_PLACEHOLDER}
          type="search"
          value={q}
        />
      </div>
      {rows.length === 0 ? (
        <p className={styles.empty}>
          <Icon name="document" size={20} />
          <button className={styles.first} onClick={onAdd} type="button">
            {EMPTY_LINK}
          </button>
        </p>
      ) : (
        <TemplatesTable
          onDelete={onDelete}
          onEdit={onEdit}
          onSort={(key) => {
            setSort(toggleSort(sort, key));
          }}
          rows={matching(rows, q)}
          sort={sort}
        />
      )}
    </>
  );
}

function matching(rows: readonly Template[], q: string): Template[] {
  const wanted = q.trim().toLowerCase();

  return rows.filter((row) => row.name.toLowerCase().includes(wanted));
}
