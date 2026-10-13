import { useEffect, useRef, useState, type FormEvent } from "react";
import type { AddressFill, GeoKind, GeoRef } from "../../../api";
import { hasKakaoMapKey } from "../../../lib/kakaoMap";
import { KakaoMapView } from "../../map/KakaoMapView";
import { Button } from "../../ui";
import { MapPointPicker, type MapPoint, type PickedSpot, type PickerStart } from "./MapPointPicker";

export type CustomPlaceReason = "none" | "noCoords" | "failed" | "direct" | "building" | "parcel" | "pin";
/** 칸을 여는 값 - 이름은 사용자가 친 검색어, fill 은 공공데이터 지번, openAt 은 위치 찍기를 열 자리(카카오 결과 자리 - 보여 주기만, 저장하지 않는다) */
export type CustomStart = { typedName: string; fill: AddressFill | null; openAt: MapPoint | null };
export type CustomPlaceSubmit = { name: string; address: string | null; geoRef: GeoRef | null; latitude: number | null; longitude: number | null };

/* 왜 이 칸이 열렸는지 한 줄. 시안 v59 · v64 */
const INTRO: Record<CustomPlaceReason, string> = {
  none: "우리 장소 목록에서 같은 곳을 찾지 못했어요. 이름을 직접 적어 담을 수 있어요.",
  noCoords: "이 장소는 위치 정보가 없어서 우리 장소 목록과 맞춰 보지 못했어요. 이름을 직접 적어 담을 수 있어요.",
  failed: "장소를 맞춰 보지 못했어요. 이름을 직접 적어 담을 수 있어요.",
  direct: "찾는 곳의 이름을 적고, 지도에서 찾아 위치를 찍어 담을 수 있어요(위치는 선택).",
  building: "우리 장소 목록에는 없어서, 이 자리 건물의 지번으로 주소와 위치를 채웠어요. 이름만 확인하고 담으세요.",
  parcel: "우리 장소 목록에는 없어서, 이 자리 땅의 지번으로 주소와 위치를 채웠어요. 이름만 확인하고 담으세요.",
  pin: "이 자리는 주소를 바로 채우지 못했어요. 지도에서 찾거나 옮겨서 정확한 자리를 찍어 주세요. 찍은 자리의 건물 · 땅 지번으로 담겨요.",
};
const SOURCE: Record<GeoKind, string> = { building: "건물 지번", parcel: "땅 지번" };
// 카카오 결과 자리에서 지도를 연다(보여 주기만) - 처음 자동으로 열 때와 취소한 뒤 다시 열 때 같은 자리
const startAt = (openAt: MapPoint | null): PickerStart | null => (openAt ? { center: openAt, origin: "kakao" } : null);
const fromFill = (fill: AddressFill): PickedSpot => ({
  address: fill.address,
  geoRef: { kind: fill.kind, id: fill.id, pin: true },
  latitude: fill.latitude,
  longitude: fill.longitude,
});

/* 나만의 장소 - 이름은 사용자가 쓴 글(시안 v64: 사용자가 친 검색어로 미리 채운다 - 카카오 이름이 아니다), 주소 · 위치는 건물 · 땅 지번(공공데이터)뿐.
   찍은 좌표는 받지도 보내지도 않는다(데브톡 151842). 이 부품은 카카오 이름을 받는 props 가 아예 없다 */
export function CustomPlaceForm({
  reason,
  start,
  tripId,
  fallbackCenter,
  onSubmit,
  onCancel,
}: {
  reason: CustomPlaceReason;
  start: CustomStart;
  tripId: string;
  fallbackCenter: MapPoint | null;
  onSubmit: (input: CustomPlaceSubmit) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(() => start.typedName.slice(0, 100));
  // undefined = 아직 안 찍음, null = 찍었지만 지번 없음(이름만), PickedSpot = 지번(주소 · pin 이면 중심)
  const [spot, setSpot] = useState<PickedSpot | null | undefined>(() => (start.fill ? fromFill(start.fill) : undefined));
  const [pickerStart, setPickerStart] = useState<PickerStart | null>(() => (reason === "pin" ? startAt(start.openAt) : null));
  const [picking, setPicking] = useState(() => reason === "pin" && start.openAt !== null && hasKakaoMapKey());
  const nameRef = useRef<HTMLInputElement | null>(null);
  const submitRef = useRef<HTMLButtonElement | null>(null);
  // 지도를 다시 여는 단추(위치 고치기 · 다시 찍기 · 지도에서 찾아 위치 찍기 - 화면에는 하나만 있다)
  const reopenRef = useRef<HTMLButtonElement | null>(null);
  const wasPicking = useRef(picking);
  const trimmed = name.trim();

  useEffect(() => {
    // 주소가 채워져 열리면 담기 단추로(이름 · 주소가 이미 있다), 아니면 이름 칸으로. 위치 찍기로 바로 열리면 지도가 초점을 가져간다
    if (picking) return;
    if (start.fill && start.typedName) submitRef.current?.focus();
    else nameRef.current?.focus();
  }, []);

  useEffect(() => {
    // 고르기 · 취소로 지도가 닫힌 뒤 초점이 사라지지 않게: 담기가 켜져 있으면 담기로, 꺼져 있으면(이름이 비었다) 지도를 다시 여는 단추로, 그것도 없으면 이름 칸으로.
    // 꺼진 단추에는 focus() 가 먹지 않아 초점이 body 로 떨어진다
    if (wasPicking.current && !picking) {
      const add = submitRef.current;
      (add && !add.disabled ? add : (reopenRef.current ?? nameRef.current))?.focus();
    }
    wasPicking.current = picking;
  }, [picking]);

  const openPicker = (next: PickerStart | null) => {
    setPickerStart(next);
    setPicking(true);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    // 결정 26: 위치를 찍는 동안에는 담지 않는다 - 지도에 보이던 자리가 저장됐다고 믿은 채 위치 없이 담기지 않게
    if (!trimmed || picking) return;
    onSubmit({ name: trimmed, address: spot?.address ?? null, geoRef: spot?.geoRef ?? null, latitude: spot?.latitude ?? null, longitude: spot?.longitude ?? null });
  };

  return (
    <form aria-label="나만의 장소" className="custom-place-form" onSubmit={submit}>
      <p className="custom-place-intro">{INTRO[reason]}</p>
      <label className="field">
        장소 이름
        <input
          maxLength={100}
          name="custom-place-name"
          onChange={(event) => setName(event.target.value)}
          placeholder="예: 할머니 댁, 숙소 앞 편의점"
          ref={nameRef}
          value={name}
        />
      </label>
      {start.typedName && <p className="cpf-hint">내가 친 검색어로 채웠어요 · 고칠 수 있어요</p>}
      {picking ? (
        <MapPointPicker
          fallbackCenter={fallbackCenter}
          onCancel={() => setPicking(false)}
          onPick={(next) => {
            setSpot(next);
            setPicking(false);
          }}
          start={pickerStart}
          tripId={tripId}
        />
      ) : spot ? (
        <div className={`custom-place-fill${spot.geoRef.pin ? "" : " nopin"}`}>
          {spot.geoRef.pin && spot.latitude !== null && spot.longitude !== null && hasKakaoMapKey() && (
            <KakaoMapView
              ariaLabel="채운 자리"
              fallback={null}
              // 라벨은 고정 - 이름을 실으면 글자를 칠 때마다 지도를 새로 만든다(라벨이 지도 키에 들어간다)
              markers={[{ id: "fill", label: "채운 자리", latitude: spot.latitude, longitude: spot.longitude }]}
              onSelectMarker={() => undefined}
              selectedMarkerId="fill"
            />
          )}
          <div className="cpf-fill-body">
            <strong>{spot.geoRef.pin ? "주소 · 위치" : "주소"}</strong>
            <p>{spot.address}</p>
            <small>{SOURCE[spot.geoRef.kind]} · 국토교통부 공공데이터</small>
            {!spot.geoRef.pin && <small className="cpf-nopin">이 땅은 넓어서 핀 없이 주소만 담겨요</small>}
          </div>
          <span className="cpf-pair">
            {hasKakaoMapKey() && (
              <button
                className="btn sm ghost"
                onClick={() =>
                  openPicker(spot.latitude !== null && spot.longitude !== null ? { center: { latitude: spot.latitude, longitude: spot.longitude }, origin: "public" } : null)
                }
                ref={reopenRef}
                type="button"
              >
                {spot.geoRef.pin ? "위치 고치기" : "다시 찍기"}
              </button>
            )}
            <button className="btn sm ghost" onClick={() => setSpot(undefined)} type="button">
              지우기
            </button>
          </span>
        </div>
      ) : spot === null ? (
        <div className="custom-place-point">
          <span>이 자리는 지번이 없어 위치 없이 이름만 담겨요</span>
          <button className="btn sm ghost" onClick={() => openPicker(null)} ref={reopenRef} type="button">
            다시 찍기
          </button>
        </div>
      ) : (
        hasKakaoMapKey() && (
          <button className="btn sm line" onClick={() => openPicker(startAt(start.openAt))} ref={reopenRef} type="button">
            지도에서 찾아 위치 찍기
          </button>
        )
      )}
      {/* 시안 v59 · 결정 26: 위치를 찍는 동안에는 칸의 취소 · 담기를 숨긴다 - 지도의 취소 · 이 위치로와 둘씩 보이지 않게 */}
      {!picking && (
        <div className="custom-place-actions">
          <Button onClick={onCancel} variant="line">
            취소
          </Button>
          {/* 공용 Button 은 ref 를 넘기지 않는다 - 같은 클래스의 일반 button 으로 초점을 옮긴다 */}
          <button className="btn primary" disabled={!trimmed} ref={submitRef} type="submit">
            담기
          </button>
        </div>
      )}
    </form>
  );
}
