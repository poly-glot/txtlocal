import { Icon } from "@/components/Icon/Icon";

import styles from "./PhonePreview.module.css";

const PLACEHOLDER = "Type a message to see preview";
const PREVIEW_LABEL = "Message preview";

interface Props {
  body: string;
  caption?: string;
  footer?: string;
  title: string;
}

export function PhonePreview({ body, caption, footer, title }: Props) {
  return (
    <section aria-label={PREVIEW_LABEL} className={styles.preview}>
      <div className={styles.frame}>
        <div className={styles.header}>
          <Icon name="back" />
          <span className={styles.title}>{title}</span>
          <Icon name="signal" />
        </div>
        <div className={styles.screen}>
          {body === "" ? (
            <p className={styles.placeholder}>{PLACEHOLDER}</p>
          ) : (
            <p className={styles.bubble}>{body}</p>
          )}
          {footer ? <p className={styles.bubble}>{footer}</p> : null}
        </div>
      </div>
      {caption === undefined ? null : <p className={styles.caption}>{caption}</p>}
    </section>
  );
}
