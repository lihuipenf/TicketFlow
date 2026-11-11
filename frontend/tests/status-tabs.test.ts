import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import StatusTabs from "../src/components/StatusTabs.vue";

describe("工单快捷筛选", () => {
  it("选择待审核时传递真实状态并保留零计数", async () => {
    const wrapper = mount(StatusTabs, {
      props: {
        modelValue: "",
        items: [
          { value: "", label: "全部工单", count: 504 },
          { value: "pending_review", label: "待审核", count: 0 },
        ],
      },
    });
    const buttons = wrapper.findAll("button");
    expect(buttons).toHaveLength(2);
    expect(buttons[1].text()).toContain("0");
    await buttons[1].trigger("click");
    expect(wrapper.emitted("update:modelValue")?.[0]).toEqual([
      "pending_review",
    ]);
    expect(buttons[0].attributes("aria-pressed")).toBe("true");
  });
});
