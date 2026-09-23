import { Button } from "@/components/Button/Button";
import { SearchForm } from "@/components/SearchForm/SearchForm";

import styles from "./SubaccountsToolbar.module.css";

const ADD_LABEL = "ADD SUBACCOUNT";
const SEARCH_LABEL = "Search";

interface Props {
  onAdd: () => void;
  onSearch: (q: string) => void;
}

export function SubaccountsToolbar({ onAdd, onSearch }: Props) {
  return (
    <div className={styles.toolbar}>
      <div className={styles.search}>
        <SearchForm id="subaccount-search" label={SEARCH_LABEL} labelHidden onSearch={onSearch} />
      </div>
      <Button onClick={onAdd}>{ADD_LABEL}</Button>
    </div>
  );
}
