import { Panel } from "@/components/Panel/Panel";
import { StatusPanel } from "@/components/StatusPanel/StatusPanel";

import { OperationCard } from "./OperationCard";
import { groupedOperations } from "./rules";
import { useOpenApiSpec } from "./useOpenApiSpec";

import styles from "./ApiDocsScreen.module.css";

const TITLE = "API Documentation";

export function ApiDocsScreen() {
  const spec = useOpenApiSpec();

  if (spec.data === undefined) {
    return <StatusPanel title={TITLE} />;
  }
  if (spec.data.status === "ERROR") {
    return <StatusPanel error={spec.data.message} title={TITLE} />;
  }

  return (
    <Panel title={TITLE}>
      {groupedOperations(spec.data.data).map((group) => (
        <section className={styles.group} key={group.label}>
          <h3 className={styles.groupTitle}>{group.label}</h3>
          {group.operations.map((operation) => (
            <OperationCard key={`${operation.method} ${operation.path}`} operation={operation} />
          ))}
        </section>
      ))}
    </Panel>
  );
}
