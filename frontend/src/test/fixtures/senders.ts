import type {
  CatalogueNumber,
  NumberCataloguePage,
  SenderView,
  SendersView,
} from "@/api/generated/dashboard";

const OWN_NUMBER = "+447400123123";

export const SHARED_SENDER: SenderView = {
  cancelled: false,
  capabilities: ["MMS", "SMS"],
  country: "GB",
  createdAt: "2026-09-19T12:00:00Z",
  display: "Shared Number",
  kind: "SHARED",
  nickname: null,
  providerIdentity: "shared-pool",
  renewalAttempt: 0,
  senderId: "sender-shared",
  status: "READY",
  statusLabel: "Ready to use",
  value: "SHARED",
};

export const OWN_SENDER: SenderView = {
  cancelled: false,
  capabilities: ["SMS"],
  country: "GB",
  createdAt: "2026-09-19T12:00:00Z",
  display: `${OWN_NUMBER} (Own Number)`,
  kind: "OWN",
  nickname: "Sam's Phone",
  providerIdentity: null,
  renewalAttempt: 0,
  senderId: "sender-own",
  status: "READY",
  statusLabel: "Ready to use",
  value: OWN_NUMBER,
  verifiedAt: "2026-09-19T12:00:00Z",
};

export const PENDING_SENDER: SenderView = {
  ...OWN_SENDER,
  nickname: "New phone",
  senderId: "sender-pending",
  status: "PENDING_VERIFICATION",
  statusLabel: "Pending verification",
};

export const DEDICATED_NUMBER = "+447984390700";

export const DEDICATED_SENDER: SenderView = {
  cancelled: false,
  capabilities: ["SMS"],
  country: "GB",
  createdAt: "2026-09-19T12:00:00Z",
  display: DEDICATED_NUMBER,
  kind: "DEDICATED",
  monthlyPriceMicro: 2_650_000,
  nickname: null,
  providerIdentity: null,
  renewalAttempt: 0,
  renewsAt: "2026-10-19T12:00:00Z",
  senderId: "sender-dedicated",
  status: "READY",
  statusLabel: "Ready to use",
  value: DEDICATED_NUMBER,
};

export const ALPHA_SENDER: SenderView = {
  cancelled: false,
  capabilities: ["SMS"],
  country: "GB",
  createdAt: "2026-09-19T12:00:00Z",
  display: "TXTLOCAL",
  kind: "ALPHA",
  nickname: null,
  providerIdentity: null,
  renewalAttempt: 0,
  senderId: "sender-alpha",
  status: "UNDER_REVIEW",
  statusLabel: "Under review",
  useCase: "MARKETING",
  value: "TXTLOCAL",
};

export const OVERVIEW: SendersView = {
  senders: { ALPHA: [], DEDICATED: [], OWN: [OWN_SENDER], SHARED: [SHARED_SENDER] },
  smart: { GB: SHARED_SENDER.senderId },
};

export const PENDING_OVERVIEW: SendersView = {
  ...OVERVIEW,
  senders: { ...OVERVIEW.senders, OWN: [PENDING_SENDER] },
};

export const DEDICATED_OVERVIEW: SendersView = {
  ...OVERVIEW,
  senders: { ...OVERVIEW.senders, DEDICATED: [DEDICATED_SENDER] },
};

export const ALPHA_OVERVIEW: SendersView = {
  ...OVERVIEW,
  senders: { ...OVERVIEW.senders, ALPHA: [ALPHA_SENDER] },
};

export const CATALOGUE_NUMBER: CatalogueNumber = {
  capabilities: ["SMS"],
  country: "GB",
  monthlyPriceMicro: 2_650_000,
  value: DEDICATED_NUMBER,
};

export const CATALOGUE_PAGE: NumberCataloguePage = {
  numbers: [CATALOGUE_NUMBER],
  page: 1,
  totalPages: 1,
};
