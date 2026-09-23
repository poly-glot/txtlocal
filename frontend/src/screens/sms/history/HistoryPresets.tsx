import { Button } from "@/components/Button/Button";

import type { HistoryPreset } from "./rules";
import { HISTORY_PRESETS } from "./rules";

import styles from "./HistoryPresets.module.css";

const CLEAR_LABEL = "Clear";

interface Props {
  onClear: () => void;
  onPick: (preset: HistoryPreset) => void;
}

export function HistoryPresets({ onClear, onPick }: Props) {
  return (
    <div className={styles.presets}>
      {HISTORY_PRESETS.map((preset) => (
        <Button
          key={preset}
          onClick={() => {
            onPick(preset);
          }}
          variant="secondary"
        >
          {preset}
        </Button>
      ))}
      <Button onClick={onClear} variant="danger">
        {CLEAR_LABEL}
      </Button>
    </div>
  );
}
