import { MutationCache, QueryClient, useMutation, useQuery } from "@tanstack/react-query";
import type { QueryClientConfig, UseQueryOptions } from "@tanstack/react-query";

import type { Result } from "@/types";

import { callApi, useFetcher } from "./client";
import type { DataOf, InitArgs, InitOf, Method, PathOf } from "./client";

export type Operation = { [M in Method]: `${M} ${PathOf<M>}` }[Method];

type QueryOptions<T> = Omit<UseQueryOptions<Result<T>>, "queryFn" | "queryKey">;
type QueryArgs<I, T> = undefined extends I
  ? [init?: I, options?: QueryOptions<T>]
  : [init: I, options?: QueryOptions<T>];

type Stales = readonly Operation[];

const ACCOUNT_SETTINGS = [
  "get /api/app/account/settings",
  "get /api/app/account/settings/messaging",
] as const satisfies Stales;
const CAMPAIGNS = [
  "get /api/app/campaigns",
  "get /api/app/campaigns/{campaignId}",
  "get /api/app/campaigns/{campaignId}/report",
] as const satisfies Stales;
const CARDS = ["get /api/app/billing/cards"] as const satisfies Stales;
const CONTACTS = [
  "get /api/app/contacts/search",
  "get /api/app/lists",
  "get /api/app/lists/{listId}/contacts",
] as const satisfies Stales;
const DELIVERY_RULES = ["get /api/app/rules/delivery"] as const satisfies Stales;
const EMAIL_SENDERS = ["get /api/app/email-senders"] as const satisfies Stales;
const GENERAL = ["get /api/app/billing/general"] as const satisfies Stales;
const INBOUND_RULES = ["get /api/app/rules/inbound"] as const satisfies Stales;
const INBOX = [
  "get /api/app/conversations",
  "get /api/app/conversations/{peer}",
] as const satisfies Stales;
const ME = ["get /api/app/home", "get /api/app/me"] as const satisfies Stales;
const SENDERS = ["get /api/app/senders"] as const satisfies Stales;
const TEMPLATES = ["get /api/app/templates"] as const satisfies Stales;
const USERS = ["get /api/app/account/users"] as const satisfies Stales;
const WEBSITES = ["get /api/app/websites"] as const satisfies Stales;

const INVALIDATES = {
  "delete /api/app/billing/cards/{payment_method_id}": CARDS,
  "delete /api/app/campaigns/{campaignId}": CAMPAIGNS,
  "delete /api/app/email-senders/{id}": EMAIL_SENDERS,
  "delete /api/app/lists/{listId}": CONTACTS,
  "delete /api/app/rules/delivery/{ruleId}": DELIVERY_RULES,
  "delete /api/app/rules/inbound/{ruleId}": INBOUND_RULES,
  "delete /api/app/senders/{senderId}": SENDERS,
  "delete /api/app/templates/{templateId}": TEMPLATES,
  "patch /api/app/lists/{listId}": CONTACTS,
  "patch /api/app/lists/{listId}/contacts/{contactId}": CONTACTS,
  "patch /api/app/me/profile": ME,
  "post /api/app/account/users": USERS,
  "post /api/app/account/users/{userId}/api-key": USERS,
  "post /api/app/campaigns": CAMPAIGNS,
  "post /api/app/campaigns/{campaignId}/cancel": [...CAMPAIGNS, ...ME],
  "post /api/app/campaigns/{campaignId}/duplicate": CAMPAIGNS,
  "post /api/app/campaigns/{campaignId}/schedule": [...CAMPAIGNS, ...ME],
  "post /api/app/conversations/read-all": INBOX,
  "post /api/app/conversations/{peer}/close": INBOX,
  "post /api/app/conversations/{peer}/messages": INBOX,
  "post /api/app/conversations/{peer}/read": INBOX,
  "post /api/app/conversations/{peer}/reopen": INBOX,
  "post /api/app/email-senders": EMAIL_SENDERS,
  "post /api/app/lists": CONTACTS,
  "post /api/app/lists/{listId}/clean-up": CONTACTS,
  "post /api/app/lists/{listId}/contacts": CONTACTS,
  "post /api/app/lists/{listId}/contacts/bulk": CONTACTS,
  "post /api/app/lists/{listId}/contacts/import": CONTACTS,
  "post /api/app/messages/send": ME,
  "post /api/app/numbers/{number}/buy": SENDERS,
  "post /api/app/rules/delivery": DELIVERY_RULES,
  "post /api/app/rules/inbound": INBOUND_RULES,
  "post /api/app/senders/alpha": SENDERS,
  "post /api/app/senders/own": SENDERS,
  "post /api/app/senders/own/{senderId}/verify": SENDERS,
  "post /api/app/templates": TEMPLATES,
  "post /api/app/websites": WEBSITES,
  "put /api/app/account/settings": ACCOUNT_SETTINGS,
  "put /api/app/account/settings/messaging": ACCOUNT_SETTINGS,
  "put /api/app/billing/cards/{payment_method_id}/default": CARDS,
  "put /api/app/billing/general": GENERAL,
  "put /api/app/campaigns/{campaignId}": CAMPAIGNS,
  "put /api/app/rules/delivery/{ruleId}": DELIVERY_RULES,
  "put /api/app/rules/inbound/{ruleId}": INBOUND_RULES,
  "put /api/app/senders/smart/{country}": SENDERS,
  "put /api/app/templates/{templateId}": TEMPLATES,
} satisfies Partial<Record<Operation, Stales>>;

const STALE_AFTER: ReadonlyMap<string, Stales> = new Map(Object.entries(INVALIDATES));

export function useApiQuery<M extends Method, P extends PathOf<M>, I extends InitOf<M, P>>(
  method: M,
  path: P,
  ...[init, options]: QueryArgs<I, DataOf<M, P, I>>
) {
  const fetcher = useFetcher();
  return useQuery({
    ...options,
    queryFn: () => callApi<M, P, I>(fetcher, method, path, ...([init] as InitArgs<I>)),
    queryKey: apiKey(method, path, init),
  });
}

export function useApiMutation<M extends Method, P extends PathOf<M>>(method: M, path: P) {
  const fetcher = useFetcher();

  return useMutation({
    mutationFn: (init: InitOf<M, P>) =>
      callApi<M, P, InitOf<M, P>>(fetcher, method, path, ...([init] as InitArgs<InitOf<M, P>>)),
    mutationKey: [operationOf(method, path)],
  });
}

export function apiKey<M extends Method>(
  method: M,
  path: PathOf<M>,
  scope?: unknown,
): readonly unknown[] {
  return [operationOf(method, path), scope];
}

export function createQueryClient(config: QueryClientConfig = {}): QueryClient {
  const queryClient: QueryClient = new QueryClient({
    ...config,
    mutationCache: new MutationCache({
      onSettled: (_data, _error, _variables, _context, mutation) => {
        invalidate(queryClient, staleAfter(mutation.options.mutationKey));
      },
    }),
  });

  return queryClient;
}

export function invalidate(queryClient: QueryClient, operations: Stales): void {
  for (const operation of operations) {
    void queryClient.invalidateQueries({ queryKey: [operation] });
  }
}

function operationOf(method: string, path: string): string {
  return `${method} ${path}`;
}

function staleAfter(mutationKey: readonly unknown[] | undefined): Stales {
  const [operation] = mutationKey ?? [];

  return typeof operation === "string" ? (STALE_AFTER.get(operation) ?? []) : [];
}
