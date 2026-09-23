import type { UsageTabRow } from "@/api/generated/dashboard";
import { Button } from "@/components/Button/Button";
import { saveCsv } from "@/lib/download";

import { usageCsv } from "./rules";

const EXPORT_FILENAME = "usage.csv";
const EXPORT_LABEL = "EXPORT";

interface Props {
  lookup: ReadonlyMap<string, string>;
  rows: readonly UsageTabRow[];
}

export function UsageExport({ lookup, rows }: Props) {
  return (
    <Button
      onClick={() => {
        saveCsv(usageCsv(rows, lookup), EXPORT_FILENAME);
      }}
      variant="secondary"
    >
      {EXPORT_LABEL}
    </Button>
  );
}
