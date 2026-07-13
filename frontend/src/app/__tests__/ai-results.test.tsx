import { cleanup, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { appDataApi, type Trip } from "../../api";
import { getPreviewTrip } from "../../test/fixtures";
import { login, renderAppRoute } from "../../test/renderAppRoute";

describe("Travel Hunter app — AI results", () => {
  it("redirects ai-results into the integrated trip detail recommendation entry", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "55",
      title: "통합 추천 진입 여행",
      days: { 1: [], 2: [] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/ai-results?tripId=55");

      await waitFor(() => expect(screen.getAllByText("통합 추천 진입 여행").length).toBeGreaterThan(0));
      await waitFor(() => expect(getTripSpy).toHaveBeenCalledWith("55"));
      expect(document.querySelector(".ai-results-screen")).toBeNull();
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("redirects ai-results without a trip id back to trips", async () => {
    await login();
    cleanup();
    renderAppRoute("/ai-results");

    expect(await screen.findByRole("heading", { name: "내 일정" })).toBeInTheDocument();
  });
});
