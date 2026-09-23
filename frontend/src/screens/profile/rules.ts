import type { ProfileUpdate } from "@/api/generated/dashboard";

export interface ProfileDraft {
  firstName: string;
  lastName: string;
  phone: string;
}

export function toProfileUpdate(draft: ProfileDraft): ProfileUpdate {
  const update: ProfileUpdate = { firstName: draft.firstName, lastName: draft.lastName };
  if (draft.phone !== "") {
    update.phone = draft.phone;
  }

  return update;
}
