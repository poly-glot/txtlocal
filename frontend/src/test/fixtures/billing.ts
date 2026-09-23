import type {
  BillingSummary,
  CardView,
  GeneralSettings,
  PackagesView,
  PageLedgerEntry,
  UpcomingCharge,
} from "@/api/generated/dashboard";

export const SUMMARY: BillingSummary = {
  autoRecharge: false,
  balanceMicro: 1_960_000,
  canSend: true,
  hasToppedUp: false,
  lowBalanceThresholdMicro: 5_000_000,
  rechargeAmountMicro: 20_000_000,
  trialDaysLeft: 12,
  trialEndsAt: "2026-10-03T12:00:00Z",
};

export const PACKAGES: PackagesView = {
  boosts: [
    { amountMicro: 10_000_000, code: "BOOST_10", estimate: 133 },
    { amountMicro: 30_000_000, code: "BOOST_30", estimate: 400 },
  ],
  packs: [
    {
      amountMicro: 300_000_000,
      code: "GROWTH",
      creditedMicro: 349_000_000,
      estimate: 4_650,
      name: "Growth pack",
      rateMicro: 38_700,
      savingsPct: 14,
    },
  ],
  rateMicro: 75_000,
};

export const CARDS: CardView[] = [
  {
    brand: "visa",
    cardholderName: "Demo Card",
    expMonth: 12,
    expYear: 2035,
    isDefault: true,
    last4: "4242",
    paymentMethodId: "pm_demo_4242",
  },
  {
    brand: "visa",
    cardholderName: "Demo Card",
    expMonth: 12,
    expYear: 2035,
    isDefault: false,
    last4: "0002",
    paymentMethodId: "pm_demo_0002",
  },
];

export const GENERAL: GeneralSettings = {
  alertThresholdMicro: 5_000_000,
  autoRecharge: false,
  email: "demo@txtlocal.local",
  lowBalanceThresholdMicro: 5_000_000,
  mobile: "+447700900123",
  name: "Demo Ltd",
  rechargeAmountMicro: 10_000_000,
};

export const UPCOMING_CHARGES: UpcomingCharge[] = [
  { monthlyPriceMicro: 2_650_000, renewsAt: "2026-10-19T00:00:00Z", value: "+447700900001" },
];

export const TRANSACTIONS_ROUTE = "GET /api/app/billing/transactions?order=desc";

export const TRANSACTIONS_PAGE: PageLedgerEntry = {
  items: [
    {
      amountMicro: 10_000_000,
      balanceAfterMicro: 12_000_000,
      createdAt: "2026-09-18T10:00:00Z",
      creditedMicro: 10_000_000,
      entryId: "entry-1",
      kind: "TOPUP",
      paidMicro: 9_000_000,
      ref: "top-up-1",
      stripeInvoiceNumber: "DEMO-1",
      stripeInvoiceUrl: "https://example.test/invoice/1",
    },
  ],
  nextCursor: null,
};
