import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { Policy } from "../api";
import { PolicyListCard } from "./cards";

const policy: Policy = {
  id: "photo-policy",
  slug: "photo-policy",
  label: "TR",
  tag: "Benefit",
  title: "Regional travel benefit",
  org: "Travel Hunter",
  region: "Jeonnam",
  deadline: "2026-12-31",
  amount: "20% off",
  summary: "Summary",
  match: 90,
  category: "기타",
  requirements: [],
  documents: [],
  officialUrl: null,
  applyUrl: null,
  sourceType: "external",
  photo: {
    imageUrl: "https://example.test/hero.jpg",
    thumbnailUrl: "https://example.test/thumb.jpg",
    alt: "Regional landmark",
    attribution: "Photo: KTO",
  },
};

describe("PolicyListCard photo layout", () => {
  it("marks the photo as the full-height card media", () => {
    render(
      <MemoryRouter>
        <PolicyListCard policy={policy} />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("img", { name: "Regional landmark" }).parentElement,
    ).toHaveClass("policy-list-media");
  });
});
