import { Navigate, useLocation } from "react-router";

import { BILLING_TOP_UP_PATH } from "@/lib/paths";

export function BillingIndexRedirect() {
  const { search } = useLocation();
  return <Navigate replace to={`${BILLING_TOP_UP_PATH}${search}`} />;
}
