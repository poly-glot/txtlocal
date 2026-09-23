import { useEffect, useRef } from "react";
import type { ReactNode } from "react";

import styles from "./Modal.module.css";

interface Props {
  children: ReactNode;
  labelledBy: string;
  onClose: () => void;
}

interface SlotProps {
  children: ReactNode;
}

interface TitleProps {
  children: ReactNode;
  id: string;
}

export function Modal({ children, labelledBy, onClose }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    dialog.current?.focus();

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    document.addEventListener("keydown", closeOnEscape);

    return () => {
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [onClose]);

  return (
    <div className={styles.overlay}>
      <dialog
        aria-labelledby={labelledBy}
        aria-modal="true"
        className={styles.dialog}
        open
        ref={dialog}
        tabIndex={-1}
      >
        {children}
      </dialog>
    </div>
  );
}

Modal.Header = function ModalHeader({ children }: SlotProps) {
  return <header className={styles.header}>{children}</header>;
};

Modal.Title = function ModalTitle({ children, id }: TitleProps) {
  return (
    <h2 className={styles.title} id={id}>
      {children}
    </h2>
  );
};

Modal.Body = function ModalBody({ children }: SlotProps) {
  return <div className={styles.body}>{children}</div>;
};

Modal.Footer = function ModalFooter({ children }: SlotProps) {
  return <footer className={styles.footer}>{children}</footer>;
};
