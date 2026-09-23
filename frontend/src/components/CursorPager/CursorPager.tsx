import { Button } from "@/components/Button/Button";
import type { CursorTrail } from "@/lib/useCursorTrail";

import styles from "./CursorPager.module.css";

const NEXT_LABEL = "Next";
const PREVIOUS_LABEL = "Previous";

interface Props {
  nextCursor: string | null | undefined;
  trail: CursorTrail;
}

export function CursorPager({ nextCursor, trail }: Props) {
  return (
    <div className={styles.pager}>
      <Button disabled={!trail.hasPrevious} onClick={trail.previous} variant="secondary">
        {PREVIOUS_LABEL}
      </Button>
      <Button
        disabled={!nextCursor}
        onClick={() => {
          if (nextCursor) {
            trail.next(nextCursor);
          }
        }}
        variant="secondary"
      >
        {NEXT_LABEL}
      </Button>
    </div>
  );
}
