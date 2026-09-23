import { useQuery } from "@tanstack/react-query";
import { Navigate, useSearchParams } from "react-router";

import { Button } from "@/components/Button/Button";
import { completeSignIn, redirectToSignIn } from "@/lib/auth";
import { useFetcher } from "@/api/client";

const SIGNING_IN_MSG = "Signing you in…";
const TRY_AGAIN = "Try again";

export function CallbackScreen() {
  const fetcher = useFetcher();
  const [params] = useSearchParams();
  const signIn = useQuery({
    queryFn: () => completeSignIn(params, fetcher),
    queryKey: ["auth", "callback", params.get("code")],
    staleTime: Infinity,
  });

  if (signIn.data === undefined) {
    return <p>{SIGNING_IN_MSG}</p>;
  }
  if (signIn.data.status === "ERROR") {
    return (
      <main>
        <p role="alert">{signIn.data.message}</p>
        <Button
          onClick={() => {
            void redirectToSignIn("/");
          }}
        >
          {TRY_AGAIN}
        </Button>
      </main>
    );
  }

  return <Navigate replace to={signIn.data.data} />;
}
