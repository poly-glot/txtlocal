import { useRef, useState } from "react";
import type { ChangeEvent, DragEvent } from "react";

import { Button } from "@/components/Button/Button";

import styles from "./MediaUpload.module.css";

const ACCEPTED_TYPES = ["image/gif", "image/jpeg", "image/png"];
const DROP_LABEL = "Drop file here or click to upload";
const MAX_BYTES = 1_048_576;
const MEDIA_FILE_LABEL = "Media file";
const REMOVE_LABEL = "Remove";
const SIZE_MSG = "Media is limited to 1 MB";
const SPECS_MSG = "image/jpeg, image/png or image/gif, up to 1 MB";
const TYPE_MSG = "Accepted media is image/jpeg, image/png or image/gif";
const UPLOAD_ERROR_MSG = "Could not upload this file. Try again.";

interface Props {
  mediaKey: string | null;
  onChange: (mediaKey: string | null) => void;
  upload: (file: File) => Promise<string | undefined>;
}

export function MediaUpload({ mediaKey, onChange, upload }: Props) {
  const [preview, setPreview] = useState<string>();
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const pick = async (file: File) => {
    setError(undefined);
    if (!ACCEPTED_TYPES.includes(file.type)) {
      setError(TYPE_MSG);

      return;
    }
    if (file.size > MAX_BYTES) {
      setError(SIZE_MSG);

      return;
    }

    setBusy(true);
    const uploaded = await upload(file);
    setBusy(false);

    if (uploaded === undefined) {
      setError(UPLOAD_ERROR_MSG);

      return;
    }
    onChange(uploaded);
    setPreview(previewUrlOf(file));
  };

  const remove = () => {
    setPreview(undefined);
    setError(undefined);
    onChange(null);
  };

  if (mediaKey !== null) {
    return (
      <div className={styles.picked}>
        {preview === undefined ? null : <img alt="" className={styles.thumb} src={preview} />}
        <Button onClick={remove} variant="secondary">
          {REMOVE_LABEL}
        </Button>
      </div>
    );
  }

  return (
    <div className={styles.field}>
      <button
        className={styles.dropzone}
        disabled={busy}
        onClick={() => {
          inputRef.current?.click();
        }}
        onDragOver={(event: DragEvent<HTMLButtonElement>) => {
          event.preventDefault();
        }}
        onDrop={(event: DragEvent<HTMLButtonElement>) => {
          event.preventDefault();
          const file = event.dataTransfer.files[0];
          if (file !== undefined) {
            void pick(file);
          }
        }}
        type="button"
      >
        {DROP_LABEL}
      </button>
      <input
        accept={ACCEPTED_TYPES.join(",")}
        aria-label={MEDIA_FILE_LABEL}
        hidden
        onChange={(event: ChangeEvent<HTMLInputElement>) => {
          const file = event.target.files?.[0];
          if (file !== undefined) {
            void pick(file);
          }
        }}
        ref={inputRef}
        type="file"
      />
      <p className={styles.specs}>{SPECS_MSG}</p>
      {error === undefined ? null : (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

function previewUrlOf(file: File): string | undefined {
  try {
    return URL.createObjectURL(file);
  } catch {
    return undefined;
  }
}
