import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import {
  appDataApi,
  type PlaceSearchCandidate,
  type Trip,
} from "../../api";
import { getPreviewTrip } from "../../test/fixtures";
import { login, renderAppRoute } from "../../test/renderAppRoute";

function candidate(title: string, address: string): PlaceSearchCandidate {
  return {
    id: `kakao:${title}`,
    label: title,
    title,
    meta: address,
    address,
    categoryName: "Cafe",
    categoryCode: "CE7",
    sourceProvider: "kakao",
    externalPlaceId: title,
    latitude: 33.45,
    longitude: 126.57,
    placeUrl: `https://place.map.kakao.com/${encodeURIComponent(title)}`,
  };
}

describe("Travel Hunter app trip place basket", () => {
  it("adds multiple searched places to a basket and saves them with one batch request", async () => {
    const first = candidate("Basket cafe", "1 Basket road");
    const second = candidate("Basket museum", "2 Basket road");
    const initialTrip: Trip = {
      ...getPreviewTrip(),
      id: "92",
      title: "Basket trip",
      revision: 3,
      days: { 1: [] },
      currentUserRole: "owner",
    };
    const savedTrip: Trip = {
      ...initialTrip,
      revision: 4,
      days: {
        1: [
          { id: "p1", time: "", label: first.title, meta: "1 Basket road" },
          { id: "p2", time: "", label: second.title, meta: "2 Basket road" },
        ],
      },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(initialTrip);
    const searchSpy = vi
      .spyOn(appDataApi, "searchTripPlaces")
      .mockImplementation(async (_tripId, request) =>
        request.query.includes("museum") ? [second] : [first],
      );
    const addBatchSpy = vi
      .spyOn(appDataApi, "addTripPlaces")
      .mockResolvedValue(savedTrip);
    const addSingleSpy = vi.spyOn(appDataApi, "addTripPlace");

    try {
      cleanup();
      await login();
      cleanup();
      renderAppRoute("/trips/92?day=1");
      const user = userEvent.setup();

      await waitFor(() => expect(document.body).toHaveTextContent("Basket trip"));
      await user.click(document.querySelector(".prototype-trip-action-add") as HTMLButtonElement);
      const dialog = await screen.findByRole("dialog", { name: "장소 추가" });
      const searchInput = dialog.querySelector('input[name="place-search"]') as HTMLInputElement;

      fireEvent.change(searchInput, { target: { value: "cafe" } });
      await waitFor(() =>
        expect(searchSpy).toHaveBeenLastCalledWith("92", { query: "cafe" }),
      );
      await user.click(
        await within(dialog).findByRole("button", { name: /Basket cafe/ }),
      );
      expect(await within(dialog).findByText("추가할 장소 1개")).toBeInTheDocument();

      fireEvent.change(searchInput, { target: { value: "museum" } });
      await waitFor(() =>
        expect(searchSpy).toHaveBeenLastCalledWith("92", { query: "museum" }),
      );
      await user.click(
        await within(dialog).findByRole("button", { name: /Basket museum/ }),
      );
      expect(await within(dialog).findByText("추가할 장소 2개")).toBeInTheDocument();

      await user.click(dialog.querySelector(".sheet-actions button") as HTMLButtonElement);

      await waitFor(() =>
        expect(addBatchSpy).toHaveBeenCalledWith("92", 1, {
          expectedRevision: 3,
          places: [
            expect.objectContaining({
              label: "Basket cafe",
              sourceProvider: "kakao",
              externalPlaceId: "Basket cafe",
            }),
            expect.objectContaining({
              label: "Basket museum",
              sourceProvider: "kakao",
              externalPlaceId: "Basket museum",
            }),
          ],
        }),
      );
      expect(addSingleSpy).not.toHaveBeenCalled();
    } finally {
      getTripSpy.mockRestore();
      searchSpy.mockRestore();
      addBatchSpy.mockRestore();
      addSingleSpy.mockRestore();
    }
  });
});
