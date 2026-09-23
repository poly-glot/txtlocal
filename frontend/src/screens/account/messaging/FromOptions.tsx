import type { MessagingSettings } from "@/api/generated/dashboard";
import { Select } from "@/components/Select/Select";

const BUSINESS_NAME_LABEL = "Show the 'Business Name' option on the dashboard:";
const OWN_NUMBER_LABEL = "Show the 'Your Number' option on the dashboard:";
const YES_NO = [
  { label: "No", value: "false" },
  { label: "Yes", value: "true" },
];

interface Props {
  onChange: (settings: MessagingSettings) => void;
  settings: MessagingSettings;
}

export function FromOptions({ onChange, settings }: Props) {
  return (
    <>
      <Select
        id="show-own-number"
        label={OWN_NUMBER_LABEL}
        onChange={(event) => {
          onChange({ ...settings, showOwnNumber: event.target.value === "true" });
        }}
        options={YES_NO}
        value={String(settings.showOwnNumber)}
      />
      <Select
        id="show-business-name"
        label={BUSINESS_NAME_LABEL}
        onChange={(event) => {
          onChange({ ...settings, showBusinessName: event.target.value === "true" });
        }}
        options={YES_NO}
        value={String(settings.showBusinessName)}
      />
    </>
  );
}
