import type { CreateTopUpRequest } from "@/api/generated/dashboard";
import { useApiMutation } from "@/api/queries";

export function useTopUpCheckout(onRefused: (message: string) => void) {
  const checkout = useApiMutation("post", "/api/app/billing/top-ups");
  const pendingCode = checkout.isPending ? checkout.variables.body.code : undefined;

  const buy = (request: CreateTopUpRequest) => {
    checkout.mutate(
      { body: request },
      {
        onSuccess: (result) => {
          if (result.status === "OK") {
            window.location.href = result.data.checkoutUrl;
          } else {
            onRefused(result.message);
          }
        },
      },
    );
  };

  return { buy, pendingCode };
}
