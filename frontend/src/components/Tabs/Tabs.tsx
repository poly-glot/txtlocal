import styles from "./Tabs.module.css";

interface Props<Tab extends string> {
  onSelect: (tab: Tab) => void;
  selected: Tab;
  tabs: readonly Tab[];
}

export function Tabs<Tab extends string>({ onSelect, selected, tabs }: Props<Tab>) {
  return (
    <div className={styles.tabs} role="tablist">
      {tabs.map((tab) => (
        <button
          aria-selected={tab === selected}
          className={styles.tab}
          key={tab}
          onClick={() => {
            onSelect(tab);
          }}
          role="tab"
          type="button"
        >
          {tab}
        </button>
      ))}
    </div>
  );
}
