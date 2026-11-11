<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import StatusTabs from "../components/StatusTabs.vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  Plus,
  Search,
  Refresh,
  Tickets,
  Clock,
  ChatDotRound,
  Warning,
  ArrowRight,
} from "@element-plus/icons-vue";
import { api, post, label, date } from "../api";
import StatusBadge from "../components/StatusBadge.vue";
import { useSession } from "../stores/session";
const route = useRoute(),
  router = useRouter();
const pageSize = ref(12),
  reviewTab = ref("reply"),
  ticketTable = ref<any>(null);
function toggleSelected(item: any, checked: unknown) {
  ticketTable.value?.toggleRowSelection(item, !!checked);
}
const session = useSession(),
  items = ref<any[]>([]),
  total = ref(0),
  page = ref(1),
  query = ref(""),
  filter = ref(""),
  priority = ref(""),
  stats = ref<any>({ statuses: {}, priorities: {} }),
  loading = ref(false);
const drawer = ref(false),
  detail = ref<any>(null),
  reply = ref(""),
  busy = ref(false),
  createOpen = ref(false),
  form = ref({ subject: "", content: "", customer_id: "", order_id: "" }),
  selected = ref<any[]>([]),
  users = ref<any[]>([]),
  assignee = ref("");
const canAssign = computed(() =>
  ["admin", "supervisor"].includes(session.user?.role || ""),
);
const activeJob = computed(() =>
  detail.value?.runs?.find((j: any) => ["queued", "running"].includes(j.state)),
);
const lastRun = computed(() => detail.value?.runs?.[0]);
const statusOptions = [
  "new",
  "pending_review",
  "approved",
  "replied",
  "escalated",
  "needs_information",
  "closed",
];
const queueTabs = computed(() => [
  { value: "", label: "全部工单", count: stats.value.total },
  ...statusOptions.map((value) => ({
    value,
    label: label(value),
    count:
      stats.value.total == null ? undefined : stats.value.statuses[value] || 0,
  })),
]);
let loadSequence = 0;

async function load() {
  const sequence = ++loadSequence;
  loading.value = true;
  try {
    const [result, overview] = await Promise.all([
      api(
        `/tickets?${new URLSearchParams({ q: query.value, status: filter.value, priority: priority.value, page: String(page.value), page_size: String(pageSize.value) })}`,
      ),
      api("/analytics/overview"),
    ]);
    if (sequence === loadSequence) {
      items.value = result.items;
      total.value = result.total;
      stats.value = overview;
    }
  } catch (e) {
    if (sequence === loadSequence) ElMessage.error((e as Error).message);
  } finally {
    if (sequence === loadSequence) loading.value = false;
  }
}
let detailSequence = 0,
  requestedTicketId = "";
async function open(id: string, reset = true) {
  const sequence = ++detailSequence;
  requestedTicketId = id;
  if (reset && route.query.ticket !== id)
    router.replace({ query: { ...route.query, ticket: id } });
  try {
    const ticket = await api("/tickets/" + id);
    if (
      sequence !== detailSequence ||
      route.path !== "/tickets" ||
      route.query.ticket !== id
    )
      return;
    detail.value = ticket;
    drawer.value = true;
    if (reset) {
      reply.value = ticket.approved_text || ticket.draft?.reply_text || "";
      reviewTab.value = "reply";
    }
    return true;
  } catch (e) {
    ElMessage.error((e as Error).message);
  }
}
function closeDetail() {
  ++detailSequence;
  requestedTicketId = "";
  const { ticket, ...query } = route.query;
  router.replace({ query });
}
async function copyReply() {
  try {
    await navigator.clipboard.writeText(reply.value);
    ElMessage.success("回复已复制");
  } catch {
    ElMessage.warning("浏览器未允许复制，请手动选中回复内容");
  }
}
watch(
  () => route.query.ticket,
  (id) => {
    if (typeof id === "string" && requestedTicketId !== id) open(id);
    else if (!id) {
      ++detailSequence;
      requestedTicketId = "";
      drawer.value = false;
    }
  },
);
async function act(task: () => Promise<unknown>) {
  const ticketId = detail.value.id;
  busy.value = true;
  try {
    await task();
    if (
      drawer.value &&
      detail.value?.id === ticketId &&
      route.query.ticket === ticketId
    )
      await open(ticketId);
    await load();
  } catch (e) {
    ElMessage.error((e as Error).message);
  } finally {
    busy.value = false;
  }
}
async function run() {
  await act(() =>
    post(`/tickets/${detail.value.id}/runs`, {
      revision: detail.value.revision,
    }),
  );
}
async function review(action: string) {
  await act(() =>
    post(`/tickets/${detail.value.id}/reviews`, {
      revision: detail.value.revision,
      action,
      text: reply.value,
    }),
  );
}
async function send() {
  try {
    await ElMessageBox.confirm(
      "将人工确认后的回复发送到模拟客服渠道。",
      "确认发送",
      { confirmButtonText: "发送回复", cancelButtonText: "取消" },
    );
    await act(() =>
      post(`/tickets/${detail.value.id}/send`, {
        revision: detail.value.revision,
      }),
    );
  } catch {}
}
async function create() {
  busy.value = true;
  try {
    const r = await post("/tickets", {
      ...form.value,
      order_id: form.value.order_id || null,
    });
    createOpen.value = false;
    form.value = { subject: "", content: "", customer_id: "", order_id: "" };
    await load();
    await open(r.id);
    ElMessage.success("工单已创建");
  } catch (e) {
    ElMessage.error((e as Error).message);
  } finally {
    busy.value = false;
  }
}
async function assign() {
  if (!assignee.value || !selected.value.length) return;
  try {
    await post("/tickets/assign/batch", {
      ticket_ids: selected.value.map((t) => t.id),
      user_id: assignee.value,
    });
    await load();
    ElMessage.success("已分配工单");
  } catch (e) {
    ElMessage.error((e as Error).message);
  }
}
function search() {
  page.value = 1;
  load();
}
let timer: ReturnType<typeof setInterval>,
  polling = false,
  alive = true;
function updateDrawer(value: boolean) {
  if (!value) closeDetail();
}
async function poll() {
  if (polling || !alive || !drawer.value || !activeJob.value) return;
  const ticketId = detail.value.id;
  polling = true;
  try {
    const applied = await open(ticketId, false);
    if (
      applied &&
      drawer.value &&
      detail.value?.id === ticketId &&
      !activeJob.value
    ) {
      reply.value = detail.value.draft?.reply_text || "";
      await load();
    }
  } finally {
    polling = false;
  }
}
onMounted(async () => {
  await load();
  if (!alive) return;
  if (typeof route.query.ticket === "string") await open(route.query.ticket);
  if (canAssign.value) {
    try {
      users.value = await api("/users");
    } catch (e) {
      ElMessage.error((e as Error).message);
    }
  }
  if (alive) timer = setInterval(poll, 2500);
});
onUnmounted(() => {
  alive = false;
  clearInterval(timer);
  ++loadSequence;
  ++detailSequence;
});
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>工单中心</h1>
      <p>查看客户诉求，核对检索证据，确认每一条回复。</p>
    </div>
    <div class="heading-actions">
      <el-button :icon="Refresh" @click="load">刷新</el-button
      ><el-button type="primary" :icon="Plus" @click="createOpen = true"
        >新建工单</el-button
      >
    </div>
  </div>
  <div class="metrics" aria-label="工单概览">
    <div class="metric">
      <label>待处理</label
      ><strong>{{
        stats.total == null ? "—" : stats.statuses.new || 0
      }}</strong>
      <p>等待智能处理</p>
    </div>
    <div class="metric emphasis">
      <label>待人工审核</label
      ><strong>{{
        stats.total == null ? "—" : stats.statuses.pending_review || 0
      }}</strong>
      <p>核对证据与回复建议</p>
    </div>
    <div class="metric">
      <label>待发送</label
      ><strong>{{
        stats.total == null ? "—" : stats.statuses.approved || 0
      }}</strong>
      <p>已确认，尚未发送</p>
    </div>
    <div class="metric">
      <label>高优先级</label
      ><strong>{{
        stats.total == null
          ? "—"
          : (stats.priorities.P0 || 0) + (stats.priorities.P1 || 0)
      }}</strong>
      <p>P0 / P1 · 全部可见工单</p>
    </div>
  </div>
  <section class="panel">
    <div class="panel-head">
      <h3>
        工单队列 <span class="counter">{{ total }}</span>
      </h3>
      <span class="subtle">建议生成后，由你审核和发送</span>
    </div>
    <StatusTabs
      v-model="filter"
      :items="queueTabs"
      @update:model-value="search"
    />
    <div class="toolbar">
      <el-input
        v-model="query"
        aria-label="搜索工单"
        :prefix-icon="Search"
        placeholder="搜索工单主题、内容或编号"
        clearable
        @keyup.enter="search"
        @clear="search"
      /><el-select
        v-model="priority"
        aria-label="按优先级筛选"
        placeholder="全部优先级"
        clearable
        @change="search"
        ><el-option
          v-for="s in ['P0', 'P1', 'P2', 'P3']"
          :key="s"
          :value="s"
          :label="s" /></el-select
      ><el-button @click="search">查询</el-button
      ><span class="toolbar-spacer"></span>
    </div>
    <div v-if="selected.length && canAssign" class="toolbar">
      <span class="helper">已选择 {{ selected.length }} 条</span
      ><el-select v-model="assignee" placeholder="选择客服"
        ><el-option
          v-for="u in users.filter((u) => u.role !== 'knowledge')"
          :key="u.id"
          :value="u.id"
          :label="u.username" /></el-select
      ><el-button @click="assign">分配工单</el-button>
    </div>
    <el-table
      ref="ticketTable"
      class="queue-desktop"
      :data="items"
      v-loading="loading"
      @selection-change="selected = $event"
      @row-dblclick="open($event.id)"
      ><el-table-column
        v-if="canAssign"
        type="selection"
        width="44" /><el-table-column label="工单主题" min-width="220"
        ><template #default="{ row }"
          ><button type="button" class="ticket-title" @click="open(row.id)">
            {{ row.subject }}
          </button>
          <div class="ticket-id">
            #{{
              row.id.startsWith("seed")
                ? "TF-" + row.id.slice(-4)
                : row.id.slice(0, 8)
            }}
            · {{ row.customer_id }}
          </div></template
        ></el-table-column
      ><el-table-column
        prop="intent"
        label="识别意图"
        min-width="95" /><el-table-column label="优先级" width="90"
        ><template #default="{ row }"
          ><span class="priority" :class="'priority-' + row.priority">{{
            row.priority
          }}</span></template
        ></el-table-column
      ><el-table-column label="处理状态" min-width="120"
        ><template #default="{ row }"
          ><StatusBadge :status="row.status" /></template></el-table-column
      ><el-table-column label="创建时间" min-width="160"
        ><template #default="{ row }"
          ><span class="subtle">{{ date(row.created_at) }}</span></template
        ></el-table-column
      ><el-table-column width="90" label="操作"
        ><template #default="{ row }"
          ><el-button link type="primary" @click="open(row.id)"
            >处理
            <el-icon
              ><ArrowRight /></el-icon></el-button></template></el-table-column
      ><template #empty><el-empty description="没有符合条件的工单" /></template
    ></el-table>
    <div class="ticket-mobile-list" v-loading="loading">
      <article v-for="item in items" :key="item.id" class="ticket-mobile">
        <div class="ticket-mobile-head">
          <el-checkbox
            v-if="canAssign"
            :model-value="selected.some((row) => row.id === item.id)"
            :aria-label="'选择工单 ' + item.subject"
            @change="toggleSelected(item, $event)"
          /><button type="button" class="ticket-title" @click="open(item.id)">
            {{ item.subject }}</button
          ><StatusBadge :status="item.status" />
        </div>
        <div class="ticket-id">
          #{{
            item.id.startsWith("seed")
              ? "TF-" + item.id.slice(-4)
              : item.id.slice(0, 8)
          }}
          · {{ item.customer_id }}
        </div>
        <div class="ticket-mobile-meta">
          <span class="priority" :class="'priority-' + item.priority">{{
            item.priority
          }}</span
          ><span>{{ item.intent || "待识别" }}</span
          ><time>{{ date(item.created_at) }}</time>
        </div>
      </article>
      <el-empty
        v-if="!loading && !items.length"
        description="没有符合条件的工单"
      />
    </div>
    <div class="table-footer">
      <span>共 {{ total }} 条工单</span
      ><el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :page-sizes="[12, 24, 48]"
        :total="total"
        layout="sizes, prev, pager, next"
        :pager-count="5"
        @current-change="load"
        @size-change="search"
      />
    </div>
  </section>
  <el-drawer
    v-model="drawer"
    title="工单处理与人工审核"
    size="720px"
    @update:model-value="updateDrawer"
    ><template v-if="detail"
      ><div class="drawer-heading">
        <div>
          <h2>{{ detail.subject }}</h2>
          <StatusBadge :status="detail.status" />
          <span class="priority" :class="'priority-' + detail.priority">{{
            detail.priority
          }}</span>
        </div>
        <el-button
          type="primary"
          :loading="busy || !!activeJob"
          :disabled="['replied', 'closed'].includes(detail.status)"
          @click="run"
          >{{ detail.draft ? "重新生成建议" : "运行智能处理" }}</el-button
        >
      </div>
      <div class="detail-section">
        <h3>客户咨询 · {{ detail.customer_id }}</h3>
        <div class="message-bubble">{{ detail.content }}</div>
      </div>
      <div v-if="detail.order" class="detail-section">
        <h3>订单事实</h3>
        <div class="facts">
          <div><span>订单</span>{{ detail.order.id }}</div>
          <div><span>状态</span>{{ label(detail.order.status) }}</div>
          <div><span>商品</span>{{ detail.order.product }}</div>
          <div>
            <span>金额</span>¥
            {{ (detail.order.amount_cents / 100).toFixed(2) }}
          </div>
        </div>
      </div>
      <el-tabs v-model="reviewTab" class="review-tabs"
        ><el-tab-pane label="回复审核" name="reply">
          <div v-if="detail.draft" class="detail-section">
            <h3>
              回复建议 · 证据充分度 {{ detail.draft.evidence_score }} / 100
            </h3>
            <p class="helper">{{ detail.draft.score_explanation }}</p>
            <el-alert
              v-for="risk in detail.draft.risk_flags"
              :key="risk"
              :title="risk"
              type="warning"
              :closable="false"
            />
            <div class="draft-editor">
              <label for="reply-text">客户将收到的回复</label
              ><el-input
                id="reply-text"
                v-model="reply"
                type="textarea"
                :rows="7"
                :disabled="
                  busy ||
                  !!activeJob ||
                  ['replied', 'closed', 'approved'].includes(detail.status)
                "
                placeholder="编辑客户将收到的回复"
              />
            </div>
            <p v-if="detail.draft.missing_information?.length" class="helper">
              待补充：{{ detail.draft.missing_information.join("；") }}
            </p>
            <div class="detail-actions">
              <el-button :disabled="!reply" @click="copyReply"
                >复制回复</el-button
              ><el-button
                v-if="
                  ['pending_review', 'escalated', 'needs_information'].includes(
                    detail.status,
                  )
                "
                type="primary"
                :loading="busy"
                :disabled="!!activeJob || !reply.trim()"
                @click="review('approve')"
                >确认回复</el-button
              ><el-button
                v-if="detail.status === 'approved'"
                type="primary"
                :loading="busy"
                @click="send"
                >发送到模拟渠道</el-button
              ><template
                v-if="
                  ['pending_review', 'escalated', 'needs_information'].includes(
                    detail.status,
                  )
                "
                ><el-button
                  :disabled="busy || !!activeJob"
                  @click="review('escalate')"
                  >升级主管</el-button
                ><el-button
                  :disabled="busy || !!activeJob"
                  @click="review('request_information')"
                  >请求补充</el-button
                ><el-button
                  :disabled="busy || !!activeJob"
                  @click="review('reject')"
                  >退回</el-button
                ></template
              >
            </div>
            <div v-if="detail.draft.citations?.length" style="margin-top: 15px">
              <h3>回复引用</h3>
              <div
                v-for="c in detail.draft.citations"
                :key="c.chunk_id"
                class="evidence-card"
              >
                <header>
                  {{ c.source.document_name }} · {{ c.source.section }}
                </header>
                <p>“{{ c.quote }}”</p>
              </div>
            </div>
          </div>
          <div v-if="!detail.draft" class="empty">
            <el-icon size="30"><ChatDotRound /></el-icon>
            <p>还没有回复建议</p>
            <small>运行智能处理后，在此核对证据并编辑回复。</small>
          </div>
          <div class="review-notice">
            确认回复后仍需点击发送。系统不会自动向客户发送内容。
          </div>
          <div v-if="detail.sent_text" class="detail-section">
            <h3>已发送回复</h3>
            <div class="message-bubble">{{ detail.sent_text }}</div>
          </div></el-tab-pane
        ><el-tab-pane
          :label="
            '知识证据' +
            (lastRun?.result?.retrieval?.hits?.length
              ? ' · ' + lastRun.result.retrieval.hits.length
              : '')
          "
          name="evidence"
        >
          <div
            v-if="lastRun?.result?.retrieval?.hits?.length"
            class="detail-section"
          >
            <h3>
              知识检索证据 · {{ lastRun.result.retrieval.duration_ms }} ms
            </h3>
            <div
              v-for="c in lastRun.result.retrieval.hits"
              :key="c.id"
              class="evidence-card"
            >
              <header>
                <b>{{ c.source.document_name }}</b
                ><span>{{
                  c.source.page_start
                    ? "第 " + c.source.page_start + " 页"
                    : "行 " + c.source.line_start + "–" + c.source.line_end
                }}</span>
              </header>
              <p>{{ c.content }}</p>
              <small
                >{{ c.source.section }} · RRF
                {{ c.rrf_score.toFixed(4) }}</small
              >
            </div>
          </div>
          <el-empty
            v-if="!lastRun?.result?.retrieval?.hits?.length"
            description="本次任务尚无检索证据" /></el-tab-pane
        ><el-tab-pane label="处理轨迹" name="trace">
          <div v-if="lastRun" class="detail-section">
            <h3>本次处理 <StatusBadge :status="lastRun.state" /></h3>
            <div v-for="(s, i) in lastRun.steps" :key="i" class="timeline-row">
              <b>{{ Number(i) + 1 }}. {{ s.name }}</b
              ><span>{{ s.duration_ms }} ms</span>
            </div>
            <el-alert
              v-if="lastRun.error"
              :title="lastRun.error"
              type="error"
              :closable="false"
            /><el-button
              v-if="lastRun.state === 'failed'"
              size="small"
              @click="act(() => post('/jobs/' + lastRun.id + '/retry'))"
              >重试任务</el-button
            >
          </div>
          <div v-if="detail.events.length" class="detail-section">
            <h3>操作记录</h3>
            <div v-for="e in detail.events" :key="e.id" class="timeline-row">
              <b>{{ e.actor }} · {{ e.action }}</b
              ><span>{{ date(e.created_at) }}</span>
            </div>
          </div></el-tab-pane
        ></el-tabs
      ></template
    ></el-drawer
  >
  <el-dialog v-model="createOpen" title="新建客户工单" width="520px"
    ><el-form label-position="top"
      ><el-form-item label="工单主题"
        ><el-input
          v-model="form.subject"
          maxlength="180"
          placeholder="例如：订单未发货，申请退款" /></el-form-item
      ><el-form-item label="客户编号"
        ><el-input
          v-model="form.customer_id"
          placeholder="例如 C001" /></el-form-item
      ><el-form-item label="关联订单（可选）"
        ><el-input
          v-model="form.order_id"
          placeholder="例如 TF20260001，须与客户匹配" /></el-form-item
      ><el-form-item label="客户咨询"
        ><el-input
          v-model="form.content"
          type="textarea"
          :rows="5"
          maxlength="8000"
          placeholder="输入客户的完整咨询内容" /></el-form-item></el-form
    ><template #footer
      ><el-button @click="createOpen = false">取消</el-button
      ><el-button
        type="primary"
        :loading="busy"
        :disabled="
          !form.subject.trim() || !form.content.trim() || !form.customer_id
        "
        @click="create"
        >创建工单</el-button
      ></template
    ></el-dialog
  >
</template>
