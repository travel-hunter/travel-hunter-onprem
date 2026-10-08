import type { CustomPlaceInput, ItineraryPlace, PublicPlaceRef, TripPlaceUpdateRequest } from "../../api";

/* 장소 수정 창의 입력칸 · 초안 · 수정 요청 본문(카카오 운영정책 3단계, 설계 docs/superpowers/specs/2026-10-03-public-place-storage-design.md 2절).
   예전 카카오 행의 이름 · 주소 · 좌표 · 분류 · 메모는 폼 · 초안 · 요청 어디에도 옮기지 않는다 - `{ ...place }` 로 펴지 않는다.
   공공데이터 행의 이름을 고치는 것은 변환이 아니다: 이름 칸은 행이 보이는 이름(label - 고친 이름이 있으면 그 이름)으로 시작하고,
   고치면 label 하나만 보낸다. 서버가 공공데이터 이름 · 주소 · 사진 · 위치는 그대로 두고 사용자 이름만 따로 담는다(user_label). */

/** 수정 창 입력칸. meta 칸이 사용자 메모다(서버 PATCH 의 memo) - 추가 창 코드가 아직 { time, label, meta } 로 폼을 비우고 칸 이름(place-meta)을
    쥔 곳이 많아 이름을 그대로 둔다. 예전 카카오 행에서는 label · meta 를 비워 둔다 */
export type PlaceEditorForm = { time: string; label: string; meta: string };

/** localStorage 초안(2판). label · memo 는 사용자가 고친 것만 담는다. 주소 · 좌표 · 분류는 담지 않는다 */
export type PlaceEditDraft = { placeId: string; time: string; label?: string; memo?: string };

/** 예전 카카오 행 확인 화면에서 고른 바꿀 장소 - 공공데이터 후보(참조) 또는 사용자가 적은 이름(+ 찍은 위치) */
export type PlaceReplacement = { publicPlace: PublicPlaceRef } | { customPlace: CustomPlaceInput };

type MemoSource = Pick<ItineraryPlace, "meta" | "address"> & { memo?: string | null };

/** 사용자가 쓴 메모. 서버가 memo 를 따로 내려 주면 그대로, 아니면 meta 에서 가린다 -
    서버는 meta 를 '메모 → 없으면 주소' 로 채우므로(trips.py) 주소와 같으면 메모가 아니다 */
export function userMemoOf(place: MemoSource): string {
  if (place.memo !== undefined) return place.memo ?? "";
  const meta = (place.meta ?? "").trim();
  return meta && meta !== (place.address ?? "").trim() ? meta : "";
}

const text = (value: unknown) => (typeof value === "string" ? value : undefined);

export function placeEditFormFor(place: ItineraryPlace, draft: PlaceEditDraft | null): PlaceEditorForm {
  // 예전 카카오 행은 이름 · 메모를 비워 연다 - 시간만 값이 있다
  if (place.needsConfirmation) return { time: place.time ?? "", label: "", meta: "" };
  return {
    time: text(draft?.time) ?? place.time ?? "",
    label: text(draft?.label) ?? place.label,
    meta: text(draft?.memo) ?? userMemoOf(place),
  };
}

/** 초안으로 남길 것. 예전 카카오 행은 null - 초안을 남기지 않는다 */
export function placeEditDraftOf(place: ItineraryPlace, form: PlaceEditorForm): PlaceEditDraft | null {
  if (place.needsConfirmation || !place.id) return null;
  const draft: PlaceEditDraft = { placeId: place.id, time: form.time };
  if (form.label !== place.label) draft.label = form.label;
  if (form.meta !== userMemoOf(place)) draft.memo = form.meta;
  return draft;
}

/** 바뀐 칸만 담은 PATCH 본문. 바뀐 게 없으면 null(요청하지 않는다).
    공공데이터 · 나만의 장소 행은 고친 label · memo 만 담는다(publicPlace · customPlace 로 바꾸지 않는다).
    replacement 는 예전 카카오 행을 바꿀 때만 온다 - 서버가 그 장소로 바꾸며 주소 · 좌표 · 분류 · 메모를 새 값으로 채우므로 label · memo 는 보내지 않는다 */
export function placeUpdateOf(
  place: ItineraryPlace,
  form: PlaceEditorForm,
  expectedRevision: number,
  replacement?: PlaceReplacement,
): TripPlaceUpdateRequest | null {
  const update: TripPlaceUpdateRequest = { expectedRevision };
  const time = form.time.trim();
  if (time !== (place.time ?? "")) update.time = time;
  if (replacement) return { ...update, ...replacement };
  if (!place.needsConfirmation) {
    const label = form.label.trim();
    if (label !== place.label) update.label = label;
    const memo = form.meta.trim();
    if (memo !== userMemoOf(place)) update.memo = memo;
  }
  return Object.keys(update).length > 1 ? update : null;
}
