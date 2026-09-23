import type { ReactNode } from "react";

import { ariaSortOf } from "./sort";

import styles from "./Table.module.css";

export interface Column<Row> {
  align?: "end";
  header: string;
  key: string;
  render: (row: Row) => ReactNode;
  sortable?: false;
}

export interface Sort {
  direction: "asc" | "desc";
  key: string;
}

interface Props<Row> {
  columns: readonly Column<Row>[];
  emptyText: string;
  keyOf: (row: Row) => string;
  onSort?: (key: string) => void;
  rows: readonly Row[];
  sort?: Sort;
}

interface HeaderProps<Row> {
  column: Column<Row>;
  onSort: ((key: string) => void) | undefined;
}

export function Table<Row>({ columns, emptyText, keyOf, onSort, rows, sort }: Props<Row>) {
  if (rows.length === 0) {
    return <p className={styles.empty}>{emptyText}</p>;
  }

  return (
    <div className={styles.scroll}>
      <table className={styles.table}>
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                aria-sort={ariaSortOf(column.key, sort)}
                className={styles.header}
                data-align={column.align}
                key={column.key}
                scope="col"
              >
                <Header column={column} onSort={onSort} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr className={styles.row} key={keyOf(row)}>
              {columns.map((column) => (
                <td className={styles.cell} data-align={column.align} key={column.key}>
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Header<Row>({ column, onSort }: HeaderProps<Row>) {
  if (onSort === undefined || column.sortable === false) {
    return column.header;
  }

  return (
    <button
      className={styles.sortButton}
      onClick={() => {
        onSort(column.key);
      }}
      type="button"
    >
      {column.header}
    </button>
  );
}
