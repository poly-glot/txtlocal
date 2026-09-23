import { Link } from "react-router";

import { Icon } from "@/components/Icon/Icon";
import { API_DOCS_PATH } from "@/lib/paths";

import styles from "./SetupChecklist.module.css";

const DONE_LABEL = "Done";
const EMAIL_DONE = "Email verified. Your account is good to go.";
const EMAIL_TODO = "Verify your email";
const NUMBER_DONE = "All done. Your number is verified.";
const NUMBER_TODO = "Verify your number";
const SUBTITLE = "A few quick steps and you're ready to send.";
const SWITCH_LINK = "Switch your view";
const SWITCH_QUESTION = "Not sending from the dashboard?";
const TITLE = "Finish setting up your profile";
const TODO_LABEL = "To do";

interface Props {
  emailVerified: boolean;
  numberVerified: boolean;
}

interface ItemProps {
  done: boolean;
  doneText: string;
  todo: string;
}

export function SetupChecklist({ emailVerified, numberVerified }: Props) {
  return (
    <section className={styles.card}>
      <h2 className={styles.title}>{TITLE}</h2>
      <p className={styles.subtitle}>{SUBTITLE}</p>
      <ul className={styles.list}>
        <ChecklistItem done={numberVerified} doneText={NUMBER_DONE} todo={NUMBER_TODO} />
        <ChecklistItem done={emailVerified} doneText={EMAIL_DONE} todo={EMAIL_TODO} />
      </ul>
      <p className={styles.switch}>
        {SWITCH_QUESTION} <Link to={API_DOCS_PATH}>{SWITCH_LINK}</Link>
      </p>
    </section>
  );
}

function ChecklistItem({ done, doneText, todo }: ItemProps) {
  return (
    <li className={styles.item}>
      <span
        aria-label={done ? DONE_LABEL : TODO_LABEL}
        className={styles.mark}
        data-done={done}
        role="img"
      >
        {done ? <Icon name="check" size={12} /> : null}
      </span>
      <span className={styles.text}>
        <span className={styles.step}>{todo}</span>
        {done ? <span className={styles.note}>{doneText}</span> : null}
      </span>
    </li>
  );
}
