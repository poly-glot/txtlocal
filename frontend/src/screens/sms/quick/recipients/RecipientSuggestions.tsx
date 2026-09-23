import type { ContactList } from "@/api/generated/dashboard";
import { useApiQuery } from "@/api/queries";
import { PhoneNumber } from "@/components/PhoneNumber/PhoneNumber";
import { dataOf } from "@/lib/format";

import type { Recipient } from "../rules";
import {
  CONTACT_SEARCH_LIMIT,
  CONTACT_SEARCH_MIN_CHARS,
  contactRecipient,
  listRecipient,
} from "./rules";

import styles from "./RecipientSuggestions.module.css";

interface Props {
  lists: readonly ContactList[];
  onPick: (recipient: Recipient) => void;
  q: string;
}

export function RecipientSuggestions({ lists, onPick, q }: Props) {
  const hits = useApiQuery(
    "get",
    "/api/app/contacts/search",
    { params: { query: { limit: CONTACT_SEARCH_LIMIT, q } } },
    { enabled: q.length >= CONTACT_SEARCH_MIN_CHARS },
  );
  const contacts = dataOf(hits.data, []);

  return (
    <ul className={styles.suggestions}>
      {lists.map((list) => (
        <li className={styles.suggestion} key={list.listId}>
          <button
            className={styles.pick}
            onClick={() => {
              onPick(listRecipient(list));
            }}
            type="button"
          >
            <span className={styles.name}>{listRecipient(list).label}</span>
          </button>
        </li>
      ))}
      {contacts.map((hit) => (
        <li className={styles.suggestion} key={`${hit.listId}:${hit.mobile}`}>
          <button
            className={styles.pick}
            onClick={() => {
              onPick(contactRecipient(hit));
            }}
            type="button"
          >
            <span className={styles.name}>
              {hit.firstName} {hit.lastName}
            </span>{" "}
            <PhoneNumber e164={hit.mobile} />
          </button>
        </li>
      ))}
    </ul>
  );
}
