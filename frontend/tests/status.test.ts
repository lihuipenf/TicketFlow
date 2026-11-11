import { mount } from "@vue/test-utils";
import { describe, it, expect } from "vitest";
import StatusBadge from "../src/components/StatusBadge.vue";
describe("客服工作台状态", () => {
  it("区分待审核与待发送，避免误认草稿已发送", () => {
    expect(
      mount(StatusBadge, { props: { status: "pending_review" } }).text(),
    ).toBe("待审核");
    expect(mount(StatusBadge, { props: { status: "approved" } }).text()).toBe(
      "待发送",
    );
    expect(mount(StatusBadge, { props: { status: "replied" } }).text()).toBe(
      "已回复",
    );
  });
});
