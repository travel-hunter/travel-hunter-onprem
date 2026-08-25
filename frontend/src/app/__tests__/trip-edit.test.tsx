import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { appDataApi, type Trip } from "../../api";
import { getPreviewTrip } from "../../test/fixtures";
import { login, renderAppRoute } from "../../test/renderAppRoute";

describe("Travel Hunter app trip edit", () => {
  it("prefills canonical DTO dates and saves settings without parsing display dates", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "91",
      title: "Canonical date trip",
      revision: 7,
      dates: "June 1 through June 3",
      startDate: "2026-06-01",
      endDate: "2026-06-03",
      days: { 1: [], 2: [], 3: [] },
      currentUserRole: "owner",
    };
    const updatedTrip: Trip = {
      ...trip,
      title: "Updated canonical trip",
      revision: 8,
      startDate: "2026-06-02",
      endDate: "2026-06-04",
      dates: "2026-06-02 ~ 2026-06-04",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const updateSettingsSpy = vi
      .spyOn(appDataApi, "updateTripSettings")
      .mockResolvedValue(updatedTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/91/edit");
      const user = userEvent.setup();

      const titleInput = await screen.findByRole("textbox", {
        name: "Trip title",
      });
      const startInput = screen.getByLabelText("Start date");
      const endInput = screen.getByLabelText("End date");

      expect(startInput).toHaveValue("2026-06-01");
      expect(endInput).toHaveValue("2026-06-03");

      await user.clear(titleInput);
      await user.type(titleInput, "Updated canonical trip");
      await user.clear(startInput);
      await user.type(startInput, "2026-06-02");
      await user.clear(endInput);
      await user.type(endInput, "2026-06-04");
      await user.click(document.querySelector('button[type="submit"]') as HTMLButtonElement);

      await waitFor(() =>
        expect(updateSettingsSpy).toHaveBeenCalledWith("91", {
          expectedRevision: 7,
          title: "Updated canonical trip",
          startDate: "2026-06-02",
          endDate: "2026-06-04",
          overflowPlaceStrategy: "moveToLastDay",
        }),
      );
    } finally {
      getTripSpy.mockRestore();
      updateSettingsSpy.mockRestore();
    }
  });

  it("keeps viewer trips read-only on the direct edit route", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "92",
      title: "Viewer trip",
      startDate: "2026-06-01",
      endDate: "2026-06-03",
      currentUserRole: "viewer",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const updateSettingsSpy = vi.spyOn(appDataApi, "updateTripSettings");

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/92/edit");

      expect(await screen.findByText("편집 권한이 없는 일정입니다.")).toBeInTheDocument();
      expect(screen.queryByRole("form", { name: "일정 편집" })).not.toBeInTheDocument();
      expect(updateSettingsSpy).not.toHaveBeenCalled();
    } finally {
      getTripSpy.mockRestore();
      updateSettingsSpy.mockRestore();
    }
  });
});
