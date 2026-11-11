<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { onBeforeRouteLeave } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { motion } from "motion-v";
import {
  Tickets,
  PriceTag,
  Box,
  Search,
  EditPen,
  DocumentChecked,
  ArrowRight,
} from "@element-plus/icons-vue";
import { api } from "../api";
import { useSession } from "../stores/session";
const session = useSession(),
  config = ref<any>(null),
  busy = ref(false),
  words = ref("");
const selectedNode = ref(3),
  baseline = ref("");
const snapshot = () =>
  JSON.stringify({
    ...config.value,
    urgent_words: words.value
      .split(/[,，]/)
      .map((w) => w.trim())
      .filter(Boolean),
  });
const dirty = computed(() => !!config.value && snapshot() !== baseline.value);
const editable = computed(() =>
  ["admin", "supervisor"].includes(session.user?.role || ""),
);
const nodes = [
  {
    title: "咨询接入",
    subtitle: "清洗与脱敏",
    icon: Tickets,
    description: "统一接收客户咨询，清洗文本并脱敏，保留处理记录。",
  },
  {
    title: "意图识别",
    subtitle: "规则与优先级",
    icon: PriceTag,
    description: "判断咨询意图与 P0–P3 优先级，识别需要优先跟进的风险。",
  },
  {
    title: "订单查询",
    subtitle: "只读事实工具",
    icon: Box,
    description: "通过关联客户与订单获取交易、物流事实，避免回复依赖猜测。",
  },
  {
    title: "混合检索",
    subtitle: "向量 + BM25",
    icon: Search,
    description:
      "并行召回语义与关键词候选，经 RRF 融合，保留文档、章节、页码等来源。",
  },
  {
    title: "回复生成",
    subtitle: "引用与规则校验",
    icon: EditPen,
    description:
      "基于检索证据与订单事实生成回复，校验引用，标记证据不足与风险。",
  },
  {
    title: "人工确认",
    subtitle: "审核后发送",
    icon: DocumentChecked,
    description:
      "客服检查证据、编辑并确认回复，再主动发送到模拟渠道。AI 不会自动发送。",
  },
];
async function load() {
  try {
    config.value = await api("/workflow/config");
    words.value = config.value.urgent_words.join("，");
    baseline.value = snapshot();
  } catch (e) {
    ElMessage.error((e as Error).message);
  }
}
async function save() {
  busy.value = true;
  try {
    config.value = await api("/workflow/config", {
      method: "PUT",
      body: JSON.stringify({
        ...config.value,
        urgent_words: words.value
          .split(/[,，]/)
          .map((w) => w.trim())
          .filter(Boolean),
      }),
    });
    words.value = config.value.urgent_words.join("，");
    baseline.value = snapshot();
    ElMessage.success("配置已发布，新任务将使用此版本");
  } catch (e) {
    ElMessage.error((e as Error).message);
  } finally {
    busy.value = false;
  }
}
function reset() {
  if (!baseline.value) return;
  config.value = JSON.parse(baseline.value);
  words.value = config.value.urgent_words.join("，");
}
onBeforeRouteLeave(async () => {
  if (!dirty.value || !session.user) return true;
  try {
    await ElMessageBox.confirm(
      "修改尚未发布，离开后将丢失这些修改。",
      "离开流程配置？",
      {
        confirmButtonText: "放弃修改并离开",
        cancelButtonText: "继续编辑",
        type: "warning",
      },
    );
    return true;
  } catch {
    return false;
  }
});
function beforeUnload(event: BeforeUnloadEvent) {
  if (dirty.value) {
    event.preventDefault();
    event.returnValue = "";
  }
}
onMounted(() => {
  load();
  window.addEventListener("beforeunload", beforeUnload);
});
onUnmounted(() => window.removeEventListener("beforeunload", beforeUnload));
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>流程配置</h1>
      <p>从客户问题到人工确认，清晰掌握每一个处理环节。</p>
    </div>
    <div v-if="editable" class="heading-actions">
      <span v-if="dirty" class="dirty-label" role="status">有未发布的修改</span
      ><el-button :disabled="!dirty || busy" @click="reset">撤销修改</el-button
      ><el-button
        type="primary"
        :loading="busy"
        :disabled="!dirty"
        @click="save"
        >发布新配置</el-button
      >
    </div>
  </div>
  <section class="panel">
    <div class="panel-head">
      <h3>电商客服处理流程</h3>
      <span class="counter">配置版本 v{{ config?.revision ?? "—" }}</span>
    </div>
    <div class="flow-canvas" role="group" aria-label="查看处理步骤">
      <template v-for="(n, i) in nodes" :key="n.title"
        ><button
          type="button"
          class="flow-node"
          :class="{ active: selectedNode === i }"
          :aria-pressed="selectedNode === i"
          @click="selectedNode = i"
        >
          <motion.span
            v-if="selectedNode === i"
            class="flow-selection"
            layout-id="workflow-selection"
            :transition="{ type: 'spring', stiffness: 440, damping: 40 }"
            aria-hidden="true"
          /><el-icon class="flow-node-icon"><component :is="n.icon" /></el-icon
          ><b>{{ i + 1 }}. {{ n.title }}</b
          ><small>{{ n.subtitle }}</small></button
        ><el-icon v-if="i < nodes.length - 1" class="flow-arrow"
          ><ArrowRight /></el-icon
      ></template>
    </div>
    <div class="node-description" aria-live="polite">
      <b>{{ nodes[selectedNode]!.title }}</b>
      <p>{{ nodes[selectedNode]!.description }}</p>
    </div>
  </section>
  <div v-if="config" class="split-grid" style="margin-top: 22px">
    <section class="panel">
      <div class="panel-head">
        <h3>混合检索参数</h3>
        <span class="subtle">RRF 融合 · k = 60</span>
      </div>
      <div class="panel-body">
        <el-form label-position="top" :disabled="!editable || busy"
          ><div class="form-grid">
            <el-form-item label="向量召回 Top K"
              ><el-input-number
                v-model="config.vector_top_k"
                :min="1"
                :max="100" /></el-form-item
            ><el-form-item label="BM25 召回 Top K"
              ><el-input-number
                v-model="config.bm25_top_k"
                :min="1"
                :max="100" /></el-form-item
            ><el-form-item label="最终上下文片段数"
              ><el-input-number
                v-model="config.context_top_k"
                :min="1"
                :max="12" /></el-form-item
            ><el-form-item label="向量最低相似度"
              ><el-input-number
                v-model="config.min_similarity"
                :min="0"
                :max="1"
                :step="0.05"
                :precision="2" /></el-form-item
            ><el-form-item label="切块最大字符数"
              ><el-input-number
                v-model="config.chunk_chars"
                :min="200"
                :max="1800"
                :step="100" /></el-form-item
            ><el-form-item label="重叠字符数"
              ><el-input-number
                v-model="config.overlap_chars"
                :min="0"
                :max="500"
                :step="20" /></el-form-item
            ><el-form-item label="上下文字符预算"
              ><el-input-number
                v-model="config.context_chars"
                :min="1000"
                :max="12000"
                :step="500"
            /></el-form-item></div
        ></el-form>
        <p class="helper">
          切块遵循标题、段落与句子边界。修改切块配置仅影响之后导入的文档；已有知识需上传新版本重建索引。
        </p>
      </div>
    </section>
    <div class="stack">
      <section class="panel">
        <div class="panel-head"><h3>优先级与人工审核</h3></div>
        <div class="panel-body">
          <el-form label-position="top"
            ><el-form-item label="P1 紧急关键词（逗号分隔）"
              ><el-input
                v-model="words"
                type="textarea"
                :rows="3"
                :disabled="!editable || busy" /></el-form-item
          ></el-form>
          <div class="timeline-row">
            <b>P0 · 安全与重大资金事件</b><span>主管审核</span>
          </div>
          <div class="timeline-row">
            <b>P1 · 紧急与超时投诉</b><span>优先跟进</span>
          </div>
          <div class="timeline-row">
            <b>P2 · 交易与售后</b><span>常规处理</span>
          </div>
          <div class="timeline-row">
            <b>P3 · 一般咨询</b><span>知识辅助</span>
          </div>
        </div>
      </section>
      <section class="panel">
        <div class="panel-body">
          <h3>每个任务保留自己的配置快照</h3>
          <p class="helper">
            新配置不会改变运行中的任务。所有生成建议必须经过人工确认，知识库证据和订单状态变化时需要重新审核。
          </p>
          <p class="helper">
            模型供应商、模型名称与 API 凭据在服务端 .env
            中管理。界面不接收或展示密钥。
          </p>
        </div>
      </section>
    </div>
  </div>
</template>
