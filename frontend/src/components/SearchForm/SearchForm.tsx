import { useState } from "react";

import { Input } from "@/components/Input/Input";

const DEFAULT_PLACEHOLDER = "Search...";

interface Props {
  id: string;
  label: string;
  labelHidden?: boolean;
  onSearch: (q: string) => void;
  placeholder?: string;
}

export function SearchForm({
  id,
  label,
  labelHidden = false,
  onSearch,
  placeholder = DEFAULT_PLACEHOLDER,
}: Props) {
  const [draft, setDraft] = useState("");

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        onSearch(draft);
      }}
      role="search"
    >
      <Input
        id={id}
        label={label}
        labelHidden={labelHidden}
        onChange={(event) => {
          setDraft(event.target.value);
        }}
        placeholder={placeholder}
        type="search"
        value={draft}
      />
    </form>
  );
}
