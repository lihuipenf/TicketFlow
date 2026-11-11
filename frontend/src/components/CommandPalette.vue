<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import {
  Search,
  Right,
  Tickets,
  Connection,
  Collection,
  DataAnalysis,
  Box,
} from "@element-plus/icons-vue";
import { api } from "../api";
import { searchNavigation } from "../navigation";
import { useSession } from "../stores/session";

const props = defineProps<{ modelValue: boolean }>();
const emit = defineEmits<{
  "update:modelValue": [value: boolean];
  navigate: [path: string, ticket?: string];
}>();
const session = useSession();
const query = ref(""),
  selected = ref(0),
  loading = ref(false),
  error = ref("");
const input = ref<HTMLInputElement>();
const tickets = ref<any[]>([]);
const icons: Record<string, any> = {
  tickets: Tickets,
  knowledge: Collection,
  workflow: Connection,
  logs: DataAnalysis,
  orders: Box,
};
const results = computed(() => [
  ...searchNavigation(query.value, session.user?.role || "").map((item) => ({
    id: item.path.slice(1),
    title: item.name,
    description: item.description,
    path: item.path,
    icon: item.icon,
    ticket: undefined as string | undefined,
  })),
  ...tickets.value.map((ticket) => ({
    id: ticket.id,
    title: ticket.subject,
    description: `工单 · ${ticket.customer_id} · #${ticket.id.slice(0, 8)}`,
    path: "/tickets",
    icon: "tickets",
    ticket: ticket.id as string | undefined,
  })),
]);
watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      query.value = "";
      selected.value = 0;
    }
  },
);
watch(
  [query, () => props.modelValue, () => session.user?.role],
  ([value, open, role], _, cleanup) => {
    tickets.value = [];
    error.value = "";
    loading.value = false;
    selected.value = 0;
    if (
      !open ||
      !value.trim() ||
      !["admin", "supervisor", "agent"].includes(role || "")
    )
      return;
    const controller = new AbortController();
    loading.value = true;
    const timer = setTimeout(async () => {
      try {
        const data = await api(
          `/tickets?q=${encodeURIComponent(value.trim())}&page_size=6`,
          { signal: controller.signal },
        );
        if (!controller.signal.aborted) tickets.value = data.items;
      } catch (failure) {
        if (!controller.signal.aborted)
          error.value = `工单查询失败：${(failure as Error).message}`;
      } finally {
        if (!controller.signal.aborted) loading.value = false;
      }
    }, 240);
    cleanup(() => {
      clearTimeout(timer);
      controller.abort();
    });
  },
);
function choose(index: number) {
  const item = results.value[index];
  if (!item) return;
  emit("update:modelValue", false);
  emit("navigate", item.path, item.ticket);
}
function keyboard(event: KeyboardEvent) {
  if (event.isComposing) return;
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    selected.value = results.value.length
      ? (selected.value +
          (event.key === "ArrowDown" ? 1 : -1) +
          results.value.length) %
        results.value.length
      : 0;
    nextTick(() =>
      document
        .getElementById(`command-${results.value[selected.value]?.id}`)
        ?.scrollIntoView({ block: "nearest" }),
    );
  } else if (event.key === "Enter") {
    event.preventDefault();
    choose(selected.value);
  }
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="快捷搜索"
    :show-close="false"
    class="command-dialog"
    width="560px"
    align-center
    @update:model-value="emit('update:modelValue', $event)"
    @opened="input?.focus()"
  >
    <div class="command-search">
      <el-icon aria-hidden="true"><Search /></el-icon
      ><input
        ref="input"
        v-model="query"
        placeholder="搜索页面、工单主题或编号…"
        aria-label="快捷搜索"
        role="combobox"
        aria-autocomplete="list"
        aria-controls="command-results"
        :aria-expanded="modelValue"
        :aria-activedescendant="
          results[selected] ? `command-${results[selected].id}` : undefined
        "
        @keydown="keyboard"
      /><button
        type="button"
        class="keycap"
        aria-label="关闭快捷搜索"
        @click="emit('update:modelValue', false)"
      >
        Esc
      </button>
    </div>
    <div
      class="command-results"
      id="command-results"
      role="listbox"
      aria-label="搜索结果"
      :aria-busy="loading"
    >
      <p class="command-label">{{ query ? "搜索结果" : "前往工作区" }}</p>
      <button
        v-for="(item, index) in results"
        :id="`command-${item.id}`"
        :key="item.id"
        type="button"
        role="option"
        :aria-selected="selected === index"
        class="command-option"
        :class="{ active: selected === index }"
        @pointermove="selected = index"
        @click="choose(index)"
      >
        <span class="command-icon"
          ><el-icon aria-hidden="true"
            ><component :is="icons[item.icon]" /></el-icon></span
        ><span
          ><b>{{ item.title }}</b
          ><small>{{ item.description }}</small></span
        ><el-icon class="command-enter" aria-hidden="true"><Right /></el-icon>
      </button>
      <p v-if="loading" class="command-message" role="status">正在查询工单…</p>
      <p v-else-if="!results.length && !error" class="command-message">
        没有找到结果，试试其他主题或编号。
      </p>
      <p v-if="error" class="command-message error-text" role="alert">
        {{ error }}
      </p>
    </div>
    <div class="command-footer">
      <span><kbd>↑</kbd><kbd>↓</kbd> 选择</span
      ><span><kbd>Enter</kbd> 打开</span><span>仅搜索有权限的内容</span>
    </div>
  </el-dialog>
</template>
