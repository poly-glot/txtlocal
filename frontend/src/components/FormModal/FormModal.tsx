import { useId } from "react";
import type { ReactNode, SubmitEvent } from "react";

import { Modal } from "@/components/Modal/Modal";
import { Toast } from "@/components/Toast/Toast";
import type { Notice } from "@/types";

interface Props {
  children: ReactNode;
  footer: ReactNode;
  notice: Notice | undefined;
  onClose: () => void;
  onDismissNotice: () => void;
  onSubmit: () => void;
  title: string;
}

export function FormModal({
  children,
  footer,
  notice,
  onClose,
  onDismissNotice,
  onSubmit,
  title,
}: Props) {
  const titleId = useId();

  const submit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSubmit();
  };

  return (
    <Modal labelledBy={titleId} onClose={onClose}>
      <form onSubmit={submit}>
        <Modal.Header>
          <Modal.Title id={titleId}>{title}</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {children}
          <Toast notice={notice} onDismiss={onDismissNotice} />
        </Modal.Body>
        <Modal.Footer>{footer}</Modal.Footer>
      </form>
    </Modal>
  );
}
