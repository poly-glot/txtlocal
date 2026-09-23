import { useId } from "react";

import { Input } from "@/components/Input/Input";
import { RowAction } from "@/components/RowAction/RowAction";

import { isValidDomain, normaliseDomain } from "./rules";

import styles from "./WebsiteDomainRow.module.css";

const DOMAIN_LABEL = "Website Domain";
const DOMAIN_PLACEHOLDER = "example.com";
const REMOVE_LABEL = "Remove website";

const previewOf = (domain: string) => `Will register as: ${domain}`;

interface Props {
  domain: string;
  hint: string | undefined;
  onChange: (value: string) => void;
  onRemove: (() => void) | undefined;
}

export function WebsiteDomainRow({ domain, hint, onChange, onRemove }: Props) {
  const id = useId();
  const normalised = normaliseDomain(domain);
  const showPreview = domain.trim() !== "" && isValidDomain(normalised);
  const helperProps = hint === undefined ? {} : { helper: hint };

  return (
    <div className={styles.row}>
      <div className={styles.field}>
        <Input
          {...helperProps}
          id={id}
          label={DOMAIN_LABEL}
          onChange={(event) => {
            onChange(event.target.value);
          }}
          placeholder={DOMAIN_PLACEHOLDER}
          value={domain}
        />
        {showPreview ? <p className={styles.preview}>{previewOf(normalised)}</p> : null}
      </div>
      {onRemove === undefined ? null : (
        <span className={styles.remove}>
          <RowAction aria-label={REMOVE_LABEL} onClick={onRemove} tone="danger">
            ×
          </RowAction>
        </span>
      )}
    </div>
  );
}
