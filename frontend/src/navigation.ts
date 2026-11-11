export interface NavigationItem {
  path: string;
  name: string;
  description: string;
  icon: string;
  keywords: string;
}

const pages: NavigationItem[] = [
  {
    path: "/tickets",
    name: "工单中心",
    description: "处理咨询、审核回复",
    icon: "tickets",
    keywords: "客服 咨询 待审核 回复 tickets",
  },
  {
    path: "/knowledge",
    name: "知识库管理",
    description: "管理政策与检索证据",
    icon: "knowledge",
    keywords: "RAG 文档 上传 检索 FAQ",
  },
  {
    path: "/workflow",
    name: "流程配置",
    description: "查看处理流程与参数",
    icon: "workflow",
    keywords: "节点 参数 配置 优先级 workflow",
  },
  {
    path: "/logs",
    name: "运行日志",
    description: "追踪任务与运行统计",
    icon: "logs",
    keywords: "统计 日志 模型 token 分析",
  },
  {
    path: "/orders",
    name: "模拟订单",
    description: "查询订单与物流状态",
    icon: "orders",
    keywords: "订单 商品 发货 物流 orders",
  },
];

export function getNavigation(role: string): NavigationItem[] {
  if (role === "admin" || role === "supervisor") return pages;
  if (role === "knowledge")
    return pages.filter((item) =>
      ["/knowledge", "/workflow"].includes(item.path),
    );
  if (role === "agent")
    return pages.filter((item) =>
      ["/tickets", "/knowledge", "/workflow"].includes(item.path),
    );
  return [];
}

export function searchNavigation(
  query: string,
  role: string,
): NavigationItem[] {
  const terms = query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  return getNavigation(role).filter((item) =>
    terms.every((term) =>
      `${item.name} ${item.description} ${item.keywords}`
        .toLocaleLowerCase()
        .includes(term),
    ),
  );
}

export function isCommandShortcut(
  event: Pick<
    KeyboardEvent,
    "key" | "ctrlKey" | "metaKey" | "altKey" | "isComposing"
  >,
): boolean {
  return (
    !event.isComposing &&
    !event.altKey &&
    (event.ctrlKey || event.metaKey) &&
    event.key.toLowerCase() === "k"
  );
}
