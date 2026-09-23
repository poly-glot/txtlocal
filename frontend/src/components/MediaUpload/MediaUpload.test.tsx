import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MediaUpload } from "./MediaUpload";

const MAX_BYTES = 1_048_576;

function picture(bytes: number, type = "image/png"): File {
  return new File([new Uint8Array(bytes)], "pic.png", { type });
}

const uploading = (key: string | undefined) => vi.fn(() => Promise.resolve(key));

describe("MediaUpload", () => {
  it("shows the accepted specs beside the dropzone", () => {
    render(<MediaUpload mediaKey={null} onChange={vi.fn()} upload={uploading("media-1")} />);

    expect(screen.getByText("image/jpeg, image/png or image/gif, up to 1 MB")).toBeInTheDocument();
  });

  it("uploads a valid file and reports the minted key", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const upload = uploading("media-1");
    const file = picture(10);
    render(<MediaUpload mediaKey={null} onChange={onChange} upload={upload} />);

    await user.upload(screen.getByLabelText("Media file"), file);

    expect(upload).toHaveBeenCalledWith(file);
    expect(onChange).toHaveBeenCalledOnce();
    expect(onChange).toHaveBeenCalledWith("media-1");
  });

  it("says so when the upload comes back without a key", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<MediaUpload mediaKey={null} onChange={onChange} upload={uploading(undefined)} />);

    await user.upload(screen.getByLabelText("Media file"), picture(10));

    expect(screen.getByRole("alert")).toHaveTextContent("Could not upload this file. Try again.");
    expect(onChange).not.toHaveBeenCalled();
  });

  it("refuses a file over the size ceiling without uploading it", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const upload = uploading("media-1");
    render(<MediaUpload mediaKey={null} onChange={onChange} upload={upload} />);

    await user.upload(screen.getByLabelText("Media file"), picture(MAX_BYTES + 1));

    expect(screen.getByRole("alert")).toHaveTextContent("Media is limited to 1 MB");
    expect(onChange).not.toHaveBeenCalled();
    expect(upload).not.toHaveBeenCalled();
  });

  it("refuses an unsupported content type without uploading it", () => {
    const onChange = vi.fn();
    const upload = uploading("media-1");
    render(<MediaUpload mediaKey={null} onChange={onChange} upload={upload} />);

    fireEvent.change(screen.getByLabelText("Media file"), {
      target: { files: [picture(10, "application/pdf")] },
    });

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Accepted media is image/jpeg, image/png or image/gif",
    );
    expect(onChange).not.toHaveBeenCalled();
    expect(upload).not.toHaveBeenCalled();
  });

  it("removing an already-picked file reports no media", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<MediaUpload mediaKey="media-1" onChange={onChange} upload={uploading("media-1")} />);

    await user.click(screen.getByRole("button", { name: "Remove" }));

    expect(onChange).toHaveBeenCalledOnce();
    expect(onChange).toHaveBeenCalledWith(null);
  });

  it("returns to the dropzone once the parent resets mediaKey to null", async () => {
    const user = userEvent.setup();
    const upload = uploading("media-1");
    const { rerender } = render(<MediaUpload mediaKey={null} onChange={vi.fn()} upload={upload} />);
    await user.upload(screen.getByLabelText("Media file"), picture(10));
    rerender(<MediaUpload mediaKey="media-1" onChange={vi.fn()} upload={upload} />);
    expect(screen.getByRole("button", { name: "Remove" })).toBeInTheDocument();

    rerender(<MediaUpload mediaKey={null} onChange={vi.fn()} upload={upload} />);

    expect(screen.getByText("Drop file here or click to upload")).toBeInTheDocument();
  });
});
