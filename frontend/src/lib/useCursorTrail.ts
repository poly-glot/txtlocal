import { useState } from "react";

interface Trail {
  cursors: readonly string[];
  scope: string;
}

export type CursorTrail = ReturnType<typeof useCursorTrail>;

export function useCursorTrail(scope: string) {
  const [trail, setTrail] = useState<Trail>({ cursors: [], scope });
  const cursors = trail.scope === scope ? trail.cursors : [];

  return {
    cursor: cursors.at(-1),
    hasPrevious: cursors.length > 0,
    next: (cursor: string) => {
      setTrail({ cursors: [...cursors, cursor], scope });
    },
    previous: () => {
      setTrail({ cursors: cursors.slice(0, -1), scope });
    },
  };
}
