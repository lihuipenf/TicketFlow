<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { ElMessage } from "element-plus";
import {
  UploadFilled,
  Search,
  Refresh,
  Document,
} from "@element-plus/icons-vue";
import { api, post, date, label } from "../api";
import StatusBadge from "../components/StatusBadge.vue";
import { useSession } from "../stores/session";
const session = useSession(),
  docs = ref<any[]>([]),
  loading = ref(false),
  uploading = ref(false),
  query = ref("还没发货，可以申请退款吗？"),
  searching = ref(false),
  job = ref<any>(null),
  chunks = ref<any[]>([]),
  preview = ref(false),
  uploadTarget = ref(""),
  input = ref<HTMLInputElement | null>(null);
const dragging = ref(false);
const canEdit = computed(() =>
  ["admin", "supervisor", "knowledge"].includes(session.user?.role || ""),
);
const result = computed(() => job.value?.result);
let alive = true,
  loadSequence = 0;
async function load() {
  const sequence = ++loadSequence;
  loading.value = true;
  try {
    const documents = await api("/knowledge/documents");
    if (alive && sequence === loadSequence) docs.value = documents;
  } catch (e) {
    ElMessage.error((e as Error).message);
  } finally {
    if (alive && sequence === loadSequence) loading.value = false;
  }
}
function choose(id = "") {
  uploadTarget.value = id;
  if (input.value) input.value.value = "";
  input.value?.click();
}
async function upload(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0];
  if (file) await uploadFile(file);
}
function drop(event: DragEvent) {
  dragging.value = false;
  if (!canEdit.value || uploading.value) return;
  uploadTarget.value = "";
  const files = event.dataTransfer?.files;
  if (files?.length !== 1) {
    ElMessage.warning("请每次上传一份文档");
    return;
  }
  uploadFile(files[0]!);
}
async function uploadFile(file: File) {
  if (uploading.value) return;
  if (!/\.(pdf|md|txt)$/i.test(file.name)) {
    ElMessage.warning("请选择 PDF、Markdown 或 TXT 文档");
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.warning("文件超过 10 MB，请拆分后上传");
    return;
  }
  uploading.value = true;
  const form = new FormData();
  form.append("file", file);
  if (uploadTarget.value) form.append("document_id", uploadTarget.value);
  try {
    await api("/knowledge/documents", { method: "POST", body: form });
    ElMessage.success("上传成功，正在排队解析与建索引");
    await load();
  } catch (e) {
    ElMessage.error((e as Error).message);
  } finally {
    uploading.value = false;
    if (input.value) input.value.value = "";
  }
}
async function publish(id: string) {
  try {
    await post("/knowledge/versions/" + id + "/publish");
    await load();
    ElMessage.success("知识版本已发布");
  } catch (e) {
    ElMessage.error((e as Error).message);
  }
}
async function disable(id: string) {
  try {
    await post("/knowledge/documents/" + id + "/disable");
    await load();
  } catch (e) {
    ElMessage.error((e as Error).message);
  }
}
async function inspect(id: string) {
  try {
    chunks.value = await api("/knowledge/versions/" + id + "/chunks");
    preview.value = true;
  } catch (e) {
    ElMessage.error((e as Error).message);
  }
}
async function search() {
  if (!query.value.trim()) return;
  searching.value = true;
  try {
    job.value = await post("/retrieval-tests", { query: query.value });
  } catch (e) {
    ElMessage.error((e as Error).message);
    searching.value = false;
  }
}
let timer: ReturnType<typeof setInterval>,
  polling = false;
onMounted(async () => {
  await load();
  if (!alive) return;
  timer = setInterval(async () => {
    if (!alive || polling) return;
    polling = true;
    try {
      if (job.value && ["queued", "running"].includes(job.value.state)) {
        const id = job.value.id;
        const latest = await api("/jobs/" + id);
        if (alive && job.value?.id === id) {
          job.value = latest;
          searching.value = ["queued", "running"].includes(latest.state);
        }
      }
      if (
        docs.value.some((d) =>
          d.versions.some((v: any) => ["queued", "indexing"].includes(v.state)),
        )
      )
        await load();
    } catch (e) {
      searching.value = false;
      if (alive) ElMessage.error((e as Error).message);
    } finally {
      polling = false;
    }
  }, 2500);
});
onUnmounted(() => {
  alive = false;
  ++loadSequence;
  clearInterval(timer);
});
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>知识库管理</h1>
      <p>管理知识版本，检验检索结果，让回复有据可查。</p>
    </div>
    <el-button :icon="Refresh" @click="load">刷新知识库</el-button>
  </div>
  <div class="metrics">
    <div class="metric">
      <label>知识文档</label
      ><strong>{{ loading && !docs.length ? "—" : docs.length }}</strong>
      <p>PDF · Markdown · TXT</p>
    </div>
    <div class="metric emphasis">
      <label>已发布文档</label
      ><strong>{{ docs.filter((d) => d.active_version).length }}</strong>
      <p>参与当前工单检索</p>
    </div>
    <div class="metric">
      <label>知识片段</label
      ><strong>{{
        docs.reduce(
          (sum, d) =>
            sum +
            d.versions.reduce(
              (s: number, v: any) => s + (v.index_meta?.chunk_count || 0),
              0,
            ),
          0,
        )
      }}</strong>
      <p>包含完整来源标记</p>
    </div>
    <div class="metric">
      <label>检索策略</label><strong class="strategy-value">混合检索</strong>
      <p>向量 + BM25 · RRF 融合</p>
    </div>
  </div>
  <div class="split-grid">
    <section class="panel">
      <div class="panel-head">
        <h3>
          文档与版本 <span class="counter">{{ docs.length }}</span>
        </h3>
        <span class="subtle">构建完成后手动发布</span>
      </div>
      <div class="panel-body" v-loading="loading">
        <input
          ref="input"
          type="file"
          accept=".pdf,.md,.txt"
          hidden
          @change="upload"
        />
        <div
          v-if="canEdit"
          class="upload-zone"
          :class="{ dragging }"
          @dragover.prevent="dragging = true"
          @dragleave.prevent="dragging = false"
          @drop.prevent="drop"
        >
          <el-icon size="27"><UploadFilled /></el-icon>
          <p>
            拖入文档，或选择文件上传<br />支持 PDF / Markdown / TXT，单文件最大
            10 MB
          </p>
          <el-button type="primary" plain :loading="uploading" @click="choose()"
            >选择文档上传</el-button
          >
        </div>
        <el-empty v-if="!docs.length" description="上传第一份知识文档" />
        <article v-for="doc in docs" :key="doc.id" class="doc-row">
          <div class="doc-title">
            <span
              ><el-icon><Document /></el-icon> {{ doc.name }}</span
            ><span
              class="status-badge"
              :class="doc.active_version ? 'status-published' : ''"
              >{{ doc.active_version ? "使用中" : "未发布" }}</span
            >
          </div>
          <div class="doc-meta">
            {{ doc.versions.length }} 个版本 · {{ date(doc.created_at) }}
          </div>
          <div
            v-for="(v, i) in doc.versions"
            :key="v.id"
            style="margin-top: 12px"
          >
            <div class="doc-actions">
              <span class="subtle"
                >v{{ doc.versions.length - Number(i) }} ·
                {{ v.index_meta?.chunk_count || 0 }} 片段</span
              ><StatusBadge :status="v.state" /><el-button
                size="small"
                text
                @click="inspect(v.id)"
                >预览片段</el-button
              ><el-button
                v-if="
                  canEdit &&
                  ['ready', 'published'].includes(v.state) &&
                  doc.active_version !== v.id
                "
                size="small"
                text
                type="primary"
                @click="publish(v.id)"
                >{{ i === 0 ? "发布版本" : "回滚至此版本" }}</el-button
              >
            </div>
            <p v-if="v.error" class="helper" style="color: #bd6b5c">
              {{ v.error }}
            </p>
          </div>
          <div v-if="canEdit" class="doc-actions" style="margin-top: 10px">
            <el-button text size="small" @click="choose(doc.id)"
              >上传新版本</el-button
            ><el-button
              v-if="doc.active_version"
              text
              size="small"
              @click="disable(doc.id)"
              >停用文档</el-button
            >
          </div>
        </article>
      </div>
    </section>
    <section class="panel">
      <div class="panel-head">
        <h3>检索实验室</h3>
        <span class="subtle">向量 + BM25 · RRF 融合</span>
      </div>
      <div class="panel-body">
        <p class="helper">
          输入客户问题，查看两个召回通道与最终证据。检索测试不调用回复生成模型。
        </p>
        <el-input
          v-model="query"
          aria-label="检索测试问题"
          type="textarea"
          :rows="3"
          placeholder="输入要验证的客户问题"
        /><el-button
          type="primary"
          :icon="Search"
          :loading="searching"
          :disabled="!query.trim()"
          class="full-width"
          style="margin: 15px 0"
          @click="search"
          >测试混合检索</el-button
        >
        <div v-if="job">
          <StatusBadge :status="job.state" /><el-alert
            v-if="job.error"
            :title="job.error"
            type="error"
            :closable="false"
          />
        </div>
        <div v-if="result">
          <div class="facts" style="margin: 15px 0">
            <div><span>总耗时</span>{{ result.duration_ms }} ms</div>
            <div><span>命中</span>{{ result.hits.length }} 个片段</div>
            <div><span>向量候选</span>{{ result.vector.length }}</div>
            <div><span>关键词候选</span>{{ result.bm25.length }}</div>
          </div>
          <el-tabs
            ><el-tab-pane label="融合证据"
              ><el-empty
                v-if="!result.hits.length"
                description="没有足够相关的知识，请补充文档或调整问题"
              />
              <div
                v-for="(hit, i) in result.hits"
                :key="hit.id"
                class="evidence-card"
              >
                <header>
                  <b>#{{ Number(i) + 1 }} {{ hit.source.document_name }}</b
                  ><span>RRF {{ hit.rrf_score.toFixed(4) }}</span>
                </header>
                <p>{{ hit.content }}</p>
                <small
                  >{{ hit.source.section }} ·
                  {{
                    hit.source.page_start
                      ? "第 " + hit.source.page_start + " 页"
                      : "行 " +
                        hit.source.line_start +
                        "–" +
                        hit.source.line_end
                  }}</small
                >
              </div></el-tab-pane
            ><el-tab-pane label="向量候选"
              ><div
                v-for="(hit, i) in result.vector"
                :key="hit.id"
                class="timeline-row"
              >
                <b>#{{ Number(i) + 1 }} {{ hit.id.slice(0, 12) }}</b
                ><span>余弦 {{ hit.score.toFixed(4) }}</span>
              </div></el-tab-pane
            ><el-tab-pane label="BM25 候选"
              ><div
                v-for="(hit, i) in result.bm25"
                :key="hit.id"
                class="timeline-row"
              >
                <b>#{{ Number(i) + 1 }} {{ hit.id.slice(0, 12) }}</b
                ><span>{{ hit.score.toFixed(4) }}</span>
              </div></el-tab-pane
            ></el-tabs
          >
        </div>
        <div v-else-if="!searching && !job?.error" class="empty">
          <el-icon size="38"><Search /></el-icon>
          <p>用一个真实问题，检验知识是否可用</p>
          <small>结果将展示来源、召回通道与融合排序</small>
        </div>
      </div>
    </section>
  </div>
  <el-drawer v-model="preview" title="知识片段预览" size="620px"
    ><div v-for="(c, i) in chunks" :key="c.id" class="evidence-card">
      <header>
        <b>片段 {{ Number(i) + 1 }} · {{ c.source.section }}</b
        ><span>{{
          c.source.page_start
            ? "第 " + c.source.page_start + " 页"
            : "行 " + c.source.line_start + "–" + c.source.line_end
        }}</span>
      </header>
      <p>{{ c.content }}</p>
      <small
        >来源：{{ c.source.document_name }} · {{ c.id.slice(0, 16) }}</small
      >
    </div>
    <el-empty v-if="!chunks.length" description="暂无片段，请等待解析完成"
  /></el-drawer>
</template>
