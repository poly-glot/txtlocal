import { Select } from "@/components/Select/Select";
import type { Option } from "@/components/Select/Select";

interface Props {
  disabled?: boolean;
  items: readonly Option[];
  label: string;
  onPick: (value: string) => void;
}

export function InsertPicker({ disabled = false, items, label, onPick }: Props) {
  return (
    <Select
      disabled={disabled}
      id={`campaign-insert-${label.toLowerCase().replace(" ", "-")}`}
      label={label}
      labelHidden
      onChange={(event) => {
        if (event.target.value !== "") {
          onPick(event.target.value);
        }
      }}
      options={[{ label, value: "" }, ...items]}
      value=""
    />
  );
}
