import type {
  AccountSettings,
  CreatedUser,
  HomeView,
  MeView,
  MessagingSettings,
  UserRow,
} from "@/api/generated/dashboard";

export const ME: MeView = {
  accountId: "account-1",
  accountName: "Demo Ltd",
  balanceMicro: 2_000_000,
  canSend: true,
  defaultCountry: "GB",
  firstName: "Demo",
  hasToppedUp: false,
  lastName: "Owner",
  phone: "+447700900123",
  role: "OWNER",
  trialDaysLeft: 12,
  trialEndsAt: "2026-10-03T12:00:00Z",
  userId: "user-1",
  username: "demo@txtlocal.local",
};

export const HOME: HomeView = {
  balanceMicro: 2_000_000,
  canSend: true,
  emailVerified: true,
  firstName: "Demo",
  lastName: "Owner",
  numberVerified: false,
  trialDaysLeft: 12,
};

export const ACCOUNT_SETTINGS: AccountSettings = {
  defaultCountry: "GB",
  name: "Demo Ltd",
  timezone: "Europe/London",
};

export const MESSAGING_SETTINGS: MessagingSettings = {
  defaultCountry: "GB",
  maxParts: 8,
  showBusinessName: true,
  showOwnNumber: true,
  unicodeMode: "AUTODETECT",
};

export const OWNER_ROW: UserRow = {
  apiKeyPrefix: "k7Qx2m9P",
  createdAt: "2026-09-19T10:00:00Z",
  firstName: "Demo",
  lastName: "Owner",
  notes: null,
  phone: "+447700900123",
  role: "OWNER",
  status: "ACTIVE",
  userId: "user-1",
  username: "demo@txtlocal.local",
};

export const SUB_ROW: UserRow = {
  apiKeyPrefix: "aB3dE5fG",
  createdAt: "2026-09-19T11:00:00Z",
  firstName: "Sam",
  lastName: "Patel",
  notes: "Support desk",
  phone: null,
  role: "SUB",
  status: "INVITED",
  userId: "user-2",
  username: "sub@txtlocal.local",
};

export const ACCOUNT_USERS: UserRow[] = [OWNER_ROW, SUB_ROW];

export const NEW_API_KEY = "k7Qx2m9PaB3dE5fGhIjKlMnOpQrStUvWxYz012345";

export const CREATED_SUBACCOUNT: CreatedUser = {
  apiKey: NEW_API_KEY,
  user: { ...SUB_ROW, userId: "user-3", username: "new@txtlocal.local" },
};
