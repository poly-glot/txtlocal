import type { Contact } from "@/api/generated/dashboard";
import { PhoneNumber } from "@/components/PhoneNumber/PhoneNumber";
import { RowAction } from "@/components/RowAction/RowAction";
import { dateTimeIn } from "@/lib/format";

import styles from "./ContactRow.module.css";

const editLabel = (mobile: string) => `Edit ${mobile}`;
const selectLabel = (mobile: string) => `Select ${mobile}`;

interface Props {
  contact: Contact;
  onEdit: (contact: Contact) => void;
  onToggle: (mobile: string) => void;
  selected: boolean;
  timezone: string | undefined;
}

export function ContactRow({ contact, onEdit, onToggle, selected, timezone }: Props) {
  return (
    <tr className={styles.row}>
      <td className={styles.cell}>
        <input
          aria-label={selectLabel(contact.mobile)}
          checked={selected}
          onChange={() => {
            onToggle(contact.mobile);
          }}
          type="checkbox"
        />
      </td>
      <td className={styles.cell}>{dateTimeIn(contact.updatedAt, timezone, "short")}</td>
      <td className={styles.cell}>{contact.firstName}</td>
      <td className={styles.cell}>{contact.lastName}</td>
      <td className={styles.cell}>
        <RowAction
          aria-label={editLabel(contact.mobile)}
          onClick={() => {
            onEdit(contact);
          }}
        >
          <PhoneNumber e164={contact.mobile} />
        </RowAction>
      </td>
      <td className={styles.cell}>{contact.email}</td>
      <td className={styles.cell}>{contact.cf1}</td>
      <td className={styles.cell}>{contact.cf2}</td>
      <td className={styles.cell}>{contact.cf3}</td>
      <td className={styles.cell}>{contact.cf4}</td>
    </tr>
  );
}
