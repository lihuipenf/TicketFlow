export async function api<T = any>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  const token = sessionStorage.getItem("ticketflow-token");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const response = await fetch("/api/v1" + path, { ...options, headers });
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401) {
      sessionStorage.removeItem("ticketflow-token");
      window.dispatchEvent(new Event("session-expired"));
    }
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "输入格式不正确，请检查必填字段",
    );
  }
  return data;
}
export const post = (path: string, body: unknown = {}) =>
  api(path, { method: "POST", body: JSON.stringify(body) });
export const labels: Record<string, string> = {
  new: "待处理",
  pending_review: "待审核",
  approved: "待发送",
  replied: "已回复",
  closed: "已关闭",
  escalated: "已升级",
  needs_information: "待补充",
  queued: "排队中",
  running: "执行中",
  succeeded: "已完成",
  failed: "失败",
  ready: "待发布",
  published: "已构建",
  indexing: "索引构建中",
  unpaid: "待付款",
  paid: "待发货",
  shipping: "运输中",
  delivered: "已签收",
  cancelled: "已取消",
  refunding: "退款中",
  refunded: "已退款",
};
export const label = (value: string) => labels[value] || value;
export const date = (value: string) =>
  new Date(value + (value.endsWith("Z") ? "" : "Z")).toLocaleString("zh-CN", {
    hour12: false,
  });
