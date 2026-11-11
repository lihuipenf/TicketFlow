<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { Refresh } from "@element-plus/icons-vue";
import { api, post, date, label } from "../api";
import StatusBadge from "../components/StatusBadge.vue";
import Chart from "../components/Chart.vue";
const stats = ref<any>({ intents: {}, statuses: {} }),
  runs = ref<any[]>([]),
  total = ref(0),
  page = ref(1),
  loading = ref(false),
  detail = ref<any>(null),
  drawer = ref(false),
  audits = ref<any[]>([]);
async function load() {
  loading.value = true;
  try {
    stats.value = await api("/analytics/overview");
    const r = await api("/runs?page=" + page.value);
    runs.value = r.items;
    total.value = r.total;
    audits.value = await api("/audit-events");
  } catch (e) {
    ElMessage.error((e as Error).message);
  } finally {
    loading.value = false;
  }
}
async function retry(id: string) {
  try {
    await post("/jobs/" + id + "/retry");
    await load();
    drawer.value = false;
    ElMessage.success("任务已重新排队");
  } catch (e) {
    ElMessage.error((e as Error).message);
  }
}
onMounted(load);
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>运行日志</h1>
      <p>理解检索表现，追踪模型调用，持续改进服务质量。</p>
    </div>
    <el-button :icon="Refresh" @click="load">刷新数据</el-button>
  </div>
  <div class="metrics">
    <div class="metric">
      <label>任务成功率</label
      ><strong>{{
        stats.success_rate == null ? "—" : stats.success_rate + "%"
      }}</strong>
      <p>
        成功 {{ stats.jobs_succeeded || 0 }} / 失败 {{ stats.jobs_failed || 0 }}
      </p>
    </div>
    <div class="metric emphasis">
      <label>平均任务耗时</label
      ><strong
        >{{
          stats.mean_duration_ms == null
            ? "—"
            : (stats.mean_duration_ms / 1000).toFixed(2)
        }}
        <small style="font-size: 13px">s</small></strong
      >
      <p>已完成任务阶段耗时之和</p>
    </div>
    <div class="metric">
      <label>模型 Token 用量</label><strong>{{ stats.tokens || 0 }}</strong>
      <p>供应商返回的实际用量</p>
    </div>
    <div class="metric">
      <label>任务记录</label><strong>{{ total }}</strong>
      <p>导入 · 检索 · 工单处理</p>
    </div>
  </div>
  <div
    class="split-grid"
    style="grid-template-columns: 1fr 1fr; margin-bottom: 22px"
  >
    <section class="panel">
      <div class="panel-head"><h3>客户意图分布</h3></div>
      <Chart :data="stats.intents" />
    </section>
    <section class="panel">
      <div class="panel-head"><h3>工单处理状态</h3></div>
      <Chart
        :data="
          Object.fromEntries(
            Object.entries(stats.statuses).map(([k, v]) => [
              label(k),
              v as number,
            ]),
          )
        "
        type="pie"
      />
    </section>
  </div>
  <section class="panel">
    <div class="panel-head">
      <h3>执行记录</h3>
      <span class="subtle">{{ stats.sample_note }}</span>
    </div>
    <el-table :data="runs" v-loading="loading"
      ><el-table-column label="任务" min-width="180"
        ><template #default="{ row }"
          ><button
            type="button"
            class="ticket-title"
            @click="
              detail = row;
              drawer = true;
            "
          >
            {{
              { ingest: "知识导入", retrieval: "混合检索", ticket: "工单处理" }[
                row.kind as string
              ] || row.kind
            }}</button
          ><span class="ticket-id">{{ row.id.slice(0, 16) }}</span></template
        ></el-table-column
      ><el-table-column label="状态" width="120"
        ><template #default="{ row }"
          ><StatusBadge :status="row.state" /></template></el-table-column
      ><el-table-column
        prop="attempts"
        label="执行次数"
        width="90"
      /><el-table-column label="耗时" width="110"
        ><template #default="{ row }"
          >{{
            row.steps.reduce((s: number, x: any) => s + x.duration_ms, 0)
          }}
          ms</template
        ></el-table-column
      ><el-table-column label="创建时间" min-width="160"
        ><template #default="{ row }"
          ><span class="subtle">{{ date(row.created_at) }}</span></template
        ></el-table-column
      ><el-table-column label="追踪" width="90"
        ><template #default="{ row }"
          ><el-button
            link
            type="primary"
            @click="
              detail = row;
              drawer = true;
            "
            >查看详情</el-button
          ></template
        ></el-table-column
      ></el-table
    >
    <div class="table-footer">
      <span>共 {{ total }} 条记录</span
      ><el-pagination
        v-model:current-page="page"
        :total="total"
        :page-size="20"
        layout="prev,pager,next"
        @current-change="load"
      />
    </div>
  </section>
  <el-drawer v-model="drawer" title="任务执行轨迹" size="650px"
    ><template v-if="detail"
      ><StatusBadge :status="detail.state" />
      <p class="helper">任务 {{ detail.id }}</p>
      <el-alert
        v-if="detail.error"
        type="error"
        :title="detail.error"
        :closable="false"
      /><el-button v-if="detail.state === 'failed'" @click="retry(detail.id)"
        >重试任务</el-button
      >
      <div
        v-for="(s, i) in detail.steps"
        :key="i"
        class="detail-section"
        style="margin-top: 20px"
      >
        <h3>{{ s.name }} · {{ s.duration_ms }} ms</h3>
        <pre class="code">{{ JSON.stringify(s.detail, null, 2) }}</pre>
      </div>
      <el-collapse
        ><el-collapse-item title="检索结果与配置快照">
          <pre class="code">{{
            JSON.stringify(
              { payload: detail.payload, result: detail.result },
              null,
              2,
            )
          }}</pre>
        </el-collapse-item></el-collapse
      ></template
    ></el-drawer
  >
  <section class="panel" style="margin-top: 22px">
    <div class="panel-head">
      <h3>最近操作审计</h3>
      <span class="subtle">最新 100 条</span>
    </div>
    <el-table :data="audits.slice(0, 10)"
      ><el-table-column
        prop="actor"
        label="操作人"
        width="130"
      /><el-table-column
        prop="action"
        label="操作"
        min-width="180"
      /><el-table-column
        prop="resource_id"
        label="关联资源"
        min-width="180"
      /><el-table-column label="时间" min-width="160"
        ><template #default="{ row }">{{
          date(row.created_at)
        }}</template></el-table-column
      ></el-table
    >
  </section>
</template>
