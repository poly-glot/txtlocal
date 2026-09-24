import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { navigatedTo, stubLocation } from "@/test/signIn";

import { LandingScreen } from "./LandingScreen";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("LandingScreen", () => {
  it("links the header's GitHub mark to the repository", () => {
    render(<LandingScreen />);

    expect(screen.getByRole("link", { name: "txtlocal on GitHub" })).toHaveAttribute(
      "href",
      "https://github.com/poly-glot/txtlocal",
    );
  });

  it("links the footer to the repository's issues", () => {
    render(<LandingScreen />);

    expect(screen.getByRole("link", { name: "Report an issue" })).toHaveAttribute(
      "href",
      "https://github.com/poly-glot/txtlocal/issues",
    );
  });

  it("links the developer section to the API reference", () => {
    render(<LandingScreen />);

    expect(screen.getByRole("link", { name: "Read the API reference" })).toHaveAttribute(
      "href",
      "https://github.com/poly-glot/txtlocal/blob/main/specs/04-developer-api.md",
    );
  });

  it("shows the send request a developer would make", () => {
    render(<LandingScreen />);

    expect(screen.getByRole("figure", { name: "Sending an SMS with curl" })).toHaveTextContent(
      "curl https://txtlocal.junaid.guru/api/v3/sms/send",
    );
  });

  it.each([
    { label: "header sign in", name: "Sign in" },
    { label: "trial call to action", name: "Start free trial" },
  ] as const)("sends the visitor to sign in from the $label", async ({ name }) => {
    const assign = stubLocation();
    render(<LandingScreen />);

    await userEvent.click(screen.getByRole("button", { name }));

    await waitFor(() => {
      expect(assign).toHaveBeenCalledOnce();
    });
    expect(navigatedTo(assign).pathname).toBe("/oauth2/authorize");
  });

  it.each([
    { label: "badge", text: "Open source · Runs on AWS Lambda" },
    { label: "trial promise", text: "£2 trial credit" },
    { label: "contract promise", text: "No contracts" },
    { label: "pricing promise", text: "Pay as you go" },
    { label: "demo progress", text: "2 of 3 delivered" },
    { label: "developers title", text: "Send your first SMS with one request" },
    {
      label: "developers lead",
      text: "The same account, balance and history as the console, over a REST API with Basic auth.",
    },
    { label: "batch point", text: "Up to 1,000 messages in one call, all or nothing" },
    { label: "schedule point", text: "Schedule any message up to 90 days ahead" },
    { label: "webhook point", text: "Signed webhooks for delivery reports and replies" },
    {
      label: "hero lead",
      text: "Send one-off texts and campaigns, answer every reply from a shared inbox, and pay only for what you send.",
    },
    { label: "features title", text: "Everything a small team needs to text customers" },
    { label: "features lead", text: "Pay as you go in pounds. No contracts and no per-seat fees." },
    { label: "campaigns", text: "Send one message or thousands, straight away or on a schedule." },
    { label: "inbox", text: "Replies land in one inbox, threaded by contact, for the whole team." },
    {
      label: "senders",
      text: "Send as your brand name, or from a dedicated number customers can reply to.",
    },
    {
      label: "receipts",
      text: "Follow every message from sent to delivered, failed or unreachable.",
    },
    {
      label: "api",
      text: "A REST API and signed webhooks to send and track messages from your own code.",
    },
    { label: "steps title", text: "From sign-up to sent in five steps" },
    { label: "steps lead", text: "Five steps, no sales call and no contract." },
    { label: "trial", text: "Every new account gets £2 of trial credit to use within 14 days." },
    { label: "sender step", text: "Register an alpha tag or buy a dedicated number." },
    { label: "import step", text: "Upload a CSV and txtlocal checks every number." },
    {
      label: "compose step",
      text: "Write once and personalise each message with fields like {first_name}.",
    },
    { label: "top-up step", text: "Pay by card through Stripe, or let auto recharge top you up." },
    { label: "benefits title", text: "Why teams choose txtlocal" },
    { label: "opt-outs", text: "Campaigns skip your opt-out list and carry an unsubscribe link." },
    { label: "pricing", text: "One rate per country, taken from your balance in pounds." },
    {
      label: "low balance",
      text: "A low-balance email before credit runs out, and auto recharge if you want it.",
    },
    { label: "screens", text: "The console fits desktop, tablet and phone." },
    { label: "open", text: "Every line is on GitHub, from the Lambda functions to this page." },
    { label: "cta title", text: "Ready to send your first message?" },
    {
      label: "cta lead",
      text: "Create an account, claim your trial credit and send your first message in minutes.",
    },
    { label: "tagline", text: "Business SMS on AWS Lambda, built in the open." },
    {
      label: "demo message",
      text: "Your order #4821 has shipped. Track it: txtlocal.junaid.guru/l/4821",
    },
    { label: "demo reply", text: "Of course. You're booked for Thursday at 10am. See you then!" },
  ] as const)("shows the $label", ({ text }) => {
    render(<LandingScreen />);

    expect(screen.getByText(text)).toBeInTheDocument();
  });
});
