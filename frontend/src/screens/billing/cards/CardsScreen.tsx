import { useApiMutation, useApiQuery } from "@/api/queries";
import { Button } from "@/components/Button/Button";
import { Panel } from "@/components/Panel/Panel";
import { StatusPanel } from "@/components/StatusPanel/StatusPanel";

import { CardsTable } from "./CardsTable";

const ADD_CARD_LABEL = "Add new card";
const TITLE = "Manage Credit Cards";

export function CardsScreen() {
  const cards = useApiQuery("get", "/api/app/billing/cards");
  const addCard = useApiMutation("post", "/api/app/billing/cards");
  const setDefault = useApiMutation("put", "/api/app/billing/cards/{payment_method_id}/default");
  const remove = useApiMutation("delete", "/api/app/billing/cards/{payment_method_id}");

  if (cards.data === undefined) {
    return <StatusPanel title={TITLE} />;
  }
  if (cards.data.status === "ERROR") {
    return <StatusPanel error={cards.data.message} title={TITLE} />;
  }

  const addNewCard = (
    <Button
      disabled={addCard.isPending}
      onClick={() => {
        addCard.mutate(undefined, {
          onSuccess: (result) => {
            if (result.status === "OK") {
              window.location.href = result.data.checkoutUrl;
            }
          },
        });
      }}
    >
      {ADD_CARD_LABEL}
    </Button>
  );

  return (
    <Panel actions={addNewCard} title={TITLE}>
      <CardsTable
        onRemove={(paymentMethodId) => {
          remove.mutate({ params: { path: { payment_method_id: paymentMethodId } } });
        }}
        onSetDefault={(paymentMethodId) => {
          setDefault.mutate({ params: { path: { payment_method_id: paymentMethodId } } });
        }}
        rows={cards.data.data}
      />
    </Panel>
  );
}
