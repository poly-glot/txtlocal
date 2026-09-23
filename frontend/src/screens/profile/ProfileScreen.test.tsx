import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { fakeFetch, refusal } from "@/test/fakeFetch";
import { ME } from "@/test/fixtures/identity";
import { renderWithProviders } from "@/test/render";

import { ProfileScreen } from "./ProfileScreen";

function renderProfile(routes: Record<string, unknown> = {}) {
  const fetcher = fakeFetch({ "GET /api/app/me": ME, "PATCH /api/app/me/profile": {}, ...routes });
  renderWithProviders(<ProfileScreen />, { fetcher });

  return fetcher;
}

describe("ProfileScreen", () => {
  it("loads the current profile with an immutable username", async () => {
    renderProfile();

    expect(await screen.findByLabelText("First Name")).toHaveValue("Demo");
    expect(screen.getByLabelText("Last Name")).toHaveValue("Owner");
    expect(screen.getByLabelText("Phone")).toHaveValue("+447700900123");
    expect(screen.getByLabelText("Username / Email")).toHaveValue("demo@txtlocal.local");
    expect(screen.getByLabelText("Username / Email")).toBeDisabled();
  });

  it("saves the profile and confirms", async () => {
    const user = userEvent.setup();
    const fetcher = renderProfile();
    const firstName = await screen.findByLabelText("First Name");

    await user.clear(firstName);
    await user.type(firstName, "Ada");
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Profile saved.")).toBeInTheDocument();
    const patch = fetcher.calls.find((call) => call.method === "PATCH");
    expect(patch).toMatchObject({
      body: { firstName: "Ada", lastName: "Owner", phone: "+447700900123" },
      path: "/api/app/me/profile",
    });
  });

  it("omits a blank phone from the update", async () => {
    const user = userEvent.setup();
    const fetcher = renderProfile();

    await user.clear(await screen.findByLabelText("Phone"));
    await user.click(screen.getByRole("button", { name: "Save" }));

    await screen.findByText("Profile saved.");
    const patch = fetcher.calls.find((call) => call.method === "PATCH");
    expect(patch?.body).toEqual({ firstName: "Demo", lastName: "Owner" });
  });

  it("renders the server's refusal verbatim", async () => {
    const user = userEvent.setup();
    renderProfile({
      "PATCH /api/app/me/profile": refusal(
        400,
        "Enter the number in international format, for example +447700900123",
      ),
    });
    await screen.findByLabelText("First Name");

    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Enter the number in international format, for example +447700900123",
    );
  });
});
