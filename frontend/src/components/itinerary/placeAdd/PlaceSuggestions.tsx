/* 장소 검색 칸 아래 완성 검색어 목록. 말은 우리 공공데이터 이름이다(카카오 값 아님) - 누르면 친 말처럼 카카오 검색에 쓰인다.
   눌러도 검색 칸의 초점이 빠지지 않게 mousedown 의 기본 동작을 막는다(초점이 빠지면 목록이 닫힌다) */
const keepInputFocus = (event: { preventDefault: () => void }) => event.preventDefault();

/* 받은 질의와 맞는 첫 자리 - 이름 맨 앞이나 공백 뒤가 먼저, 없으면 첫 부분 일치, 없으면 -1 */
function matchStart(text: string, query: string): number {
  const lowerText = text.toLowerCase();
  const lowerQuery = query.toLowerCase();
  if (lowerText.startsWith(lowerQuery)) return 0;
  const afterSpace = lowerText.indexOf(` ${lowerQuery}`);
  return afterSpace >= 0 ? afterSpace + 1 : lowerText.indexOf(lowerQuery);
}

function Highlighted({ text, query }: { text: string; query: string }) {
  const start = query ? matchStart(text, query) : -1;
  if (start < 0) return <>{text}</>;
  const end = start + query.length;
  return (
    <>
      {text.slice(0, start)}
      <strong>{text.slice(start, end)}</strong>
      {text.slice(end)}
    </>
  );
}

export function PlaceSuggestions({
  query,
  suggestions,
  onPick,
}: {
  /** 이 목록을 받은 (앞뒤 공백을 자른) 질의 */
  query: string;
  suggestions: string[];
  onPick: (text: string) => void;
}) {
  if (suggestions.length === 0) return null;
  return (
    <ul aria-label="완성 검색어" className="place-suggestions" onMouseDown={keepInputFocus}>
      {suggestions.map((text) => (
        <li key={text}>
          <button aria-label={text} className="place-suggestion" onClick={() => onPick(text)} onMouseDown={keepInputFocus} type="button">
            <Highlighted query={query} text={text} />
          </button>
        </li>
      ))}
    </ul>
  );
}
