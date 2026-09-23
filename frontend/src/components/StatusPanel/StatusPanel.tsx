import { Panel } from "@/components/Panel/Panel";
import { StatusMessage } from "@/components/StatusMessage/StatusMessage";

interface Props {
  error?: string;
  title?: string;
}

export function StatusPanel({ error, title }: Props) {
  return (
    <Panel title={title}>
      <StatusMessage error={error} />
    </Panel>
  );
}
