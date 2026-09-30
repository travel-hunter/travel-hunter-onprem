import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BenefitTile, benefitTypeOf } from "./benefitTile";

describe("benefit tile", () => {
  it("sorts policies into benefit types by title keywords, most specific first", () => {
    expect(benefitTypeOf({ title: "[영광] 2026 반값여행 숙박 환급", category: "숙박" })).toBe("refund");
    expect(benefitTypeOf({ title: "[강화] 디지털관광주민증 혜택", category: "지역할인" })).toBe("partner");
    expect(benefitTypeOf({ title: "숙박세일 페스타", category: "이벤트" })).toBe("stay");
    expect(benefitTypeOf({ title: "제주 한옥 체험", category: "숙박" })).toBe("stay");
    expect(benefitTypeOf({ title: "섬 여행 렌터카 할인", category: "교통" })).toBe("car");
    expect(benefitTypeOf({ title: "내일로패스 할인", category: "교통" })).toBe("train");
    expect(benefitTypeOf({ title: "국내선 항공권 할인", category: "교통" })).toBe("plane");
    expect(benefitTypeOf({ title: "여객선 운임 지원", category: "교통" })).toBe("ship");
    expect(benefitTypeOf({ title: "지역 여행상품 할인", category: "여행상품" })).toBe("trip");
  });

  it("is hidden from screen readers unless it has to name the benefit type itself", () => {
    const { container, rerender } = render(<BenefitTile kind="stay" />);
    expect(container.querySelector(".benefit-tile")).toHaveAttribute("aria-hidden", "true");
    rerender(<BenefitTile kind="stay" decorative={false} />);
    expect(container.querySelector(".benefit-tile")).toHaveAttribute("aria-label", "숙박 할인");
  });
});
