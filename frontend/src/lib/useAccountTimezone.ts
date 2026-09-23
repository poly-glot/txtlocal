import { useApiQuery } from "@/api/queries";

export function useAccountTimezone(): string | undefined {
  const settings = useApiQuery("get", "/api/app/account/settings");

  return settings.data?.status === "OK" ? settings.data.data.timezone : undefined;
}
