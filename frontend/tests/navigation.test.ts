import { describe, expect, it } from "vitest";
import * as navigation from "../src/navigation";

describe("工作区快捷导航", () => {
  it("知识管理员只能找到其有权限的页面", () => {
    expect(
      navigation.getNavigation("knowledge").map((item) => item.path),
    ).toEqual(["/knowledge", "/workflow"]);
    expect(navigation.searchNavigation("订单", "knowledge")).toEqual([]);
  });
  it("客服搜索不返回主管日志和订单列表", () => {
    expect(navigation.getNavigation("agent").map((item) => item.path)).toEqual([
      "/tickets",
      "/knowledge",
      "/workflow",
    ]);
    expect(navigation.searchNavigation("日志", "agent")).toEqual([]);
  });
  it("支持去除空白和检索功能关键词", () => {
    expect(
      navigation.searchNavigation("  RAG  ", "admin").map((item) => item.path),
    ).toContain("/knowledge");
    expect(
      navigation.searchNavigation("发货", "admin").map((item) => item.path),
    ).toEqual(["/orders"]);
  });
  it("输入法组词和普通按键不会打开命令面板", () => {
    expect(
      navigation.isCommandShortcut({
        key: "k",
        ctrlKey: true,
        metaKey: false,
        altKey: false,
        isComposing: true,
      }),
    ).toBe(false);
    expect(
      navigation.isCommandShortcut({
        key: "k",
        ctrlKey: false,
        metaKey: false,
        altKey: false,
        isComposing: false,
      }),
    ).toBe(false);
    expect(
      navigation.isCommandShortcut({
        key: "K",
        ctrlKey: false,
        metaKey: true,
        altKey: false,
        isComposing: false,
      }),
    ).toBe(true);
  });
});
