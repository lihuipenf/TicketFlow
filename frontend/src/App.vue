<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import {
  Tickets,
  Collection,
  Connection,
  DataAnalysis,
  Box,
  Search,
  SwitchButton,
  ArrowRight,
  Menu,
  Close,
  DocumentChecked,
  CircleCheck,
  Key,
} from "@element-plus/icons-vue";
import { MotionConfig, motion } from "motion-v";
import { useSession } from "./stores/session";
import { api } from "./api";
import { getNavigation, isCommandShortcut } from "./navigation";
import BrandMark from "./components/BrandMark.vue";
import CommandPalette from "./components/CommandPalette.vue";

const session = useSession(),
  route = useRoute(),
  router = useRouter();
const username = ref("admin"),
  password = ref(""),
  busy = ref(false),
  restoring = ref(true);
const system = ref<any>(null),
  commandOpen = ref(false),
  mobileNav = ref(false);
const mobileMedia = window.matchMedia("(max-width: 760px)"),
  isMobile = ref(mobileMedia.matches);
const sidebar = ref<HTMLElement>(),
  menuButton = ref<HTMLButtonElement>();
const updateViewport = () => {
  isMobile.value = mobileMedia.matches;
  if (!isMobile.value) mobileNav.value = false;
};
watch(mobileNav, async (open) => {
  await nextTick();
  if (open) sidebar.value?.querySelector<HTMLElement>(".mobile-close")?.focus();
  else if (isMobile.value) menuButton.value?.focus();
});
const navIcons: Record<string, any> = {
  tickets: Tickets,
  knowledge: Collection,
  workflow: Connection,
  logs: DataAnalysis,
  orders: Box,
};
const navigation = computed(() => getNavigation(session.user?.role || ""));
const active = computed(() =>
  navigation.value.find((item) => item.path === route.path),
);
const roleNames: Record<string, string> = {
  admin: "管理员",
  supervisor: "客服主管",
  agent: "客服专员",
  knowledge: "知识管理员",
};
async function refreshStatus() {
  try {
    system.value = await api("/system/status");
  } catch (failure) {
    ElMessage.error((failure as Error).message);
  }
}
function ensureRoute() {
  if (
    session.user &&
    !navigation.value.some((item) => item.path === route.path)
  )
    router.replace(navigation.value[0]?.path || "/tickets");
}
async function login() {
  busy.value = true;
  try {
    await session.login(username.value.trim(), password.value);
    password.value = "";
    ensureRoute();
    await refreshStatus();
  } catch (failure) {
    ElMessage.error((failure as Error).message);
  } finally {
    busy.value = false;
  }
}
function logout() {
  commandOpen.value = false;
  mobileNav.value = false;
  system.value = null;
  session.logout();
}
function shortcut(event: KeyboardEvent) {
  if (session.user && isCommandShortcut(event)) {
    event.preventDefault();
    mobileNav.value = false;
    commandOpen.value = !commandOpen.value;
  }
  if (event.key === "Escape") mobileNav.value = false;
  if (mobileNav.value && event.key === "Tab") {
    const controls = sidebar.value?.querySelectorAll<HTMLElement>(
      "a[href], button:not([disabled])",
    );
    if (!controls?.length) return;
    const first = controls[0]!,
      last = controls[controls.length - 1]!;
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
}
function navigate(path: string, ticket?: string) {
  mobileNav.value = false;
  router.push({ path, query: ticket ? { ticket } : {} });
}
watch(
  () => route.path,
  () => {
    mobileNav.value = false;
    ensureRoute();
  },
);
onMounted(async () => {
  window.addEventListener("session-expired", logout);
  window.addEventListener("keydown", shortcut);
  mobileMedia.addEventListener("change", updateViewport);
  try {
    await session.restore();
    if (session.user) {
      ensureRoute();
      await refreshStatus();
    }
  } catch {
    logout();
  } finally {
    restoring.value = false;
  }
});
onUnmounted(() => {
  window.removeEventListener("session-expired", logout);
  window.removeEventListener("keydown", shortcut);
  mobileMedia.removeEventListener("change", updateViewport);
});
</script>

<template>
  <MotionConfig
    reduced-motion="user"
    :transition="{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }"
  >
    <div v-if="restoring" class="session-loading" role="status">
      <BrandMark /><span>正在打开工作台…</span>
    </div>
    <div v-else-if="!session.user" class="login-scene">
      <section class="login-story">
        <div class="brand">
          <BrandMark /><span>TicketFlow<span class="brand-dot">.</span></span>
        </div>
        <div class="login-intro">
          <h1>每一份咨询，<br />都有据可依。</h1>
          <p>
            连接订单、知识与客服。<br />让 AI 整理证据，让专业的人做出决定。
          </p>
        </div>
        <div class="login-workflow" aria-label="工单处理路径">
          <div>
            <span class="login-step-icon"
              ><el-icon><Tickets /></el-icon></span
            ><span
              ><b>接收客户咨询</b><small>清洗信息，关联订单事实</small></span
            ><el-icon class="login-step-check"><CircleCheck /></el-icon>
          </div>
          <div>
            <span class="login-step-icon"
              ><el-icon><Collection /></el-icon></span
            ><span
              ><b>检索企业知识</b><small>找到政策，保留引用来源</small></span
            ><el-icon class="login-step-check"><CircleCheck /></el-icon>
          </div>
          <div class="login-review-step">
            <span class="login-step-icon"
              ><el-icon><DocumentChecked /></el-icon></span
            ><span
              ><b>人工确认回复</b><small>查看证据，确认后再发送</small></span
            ><span class="local-badge">由你决定</span>
          </div>
        </div>
        <div class="login-story-foot">
          智能电商服务工作台<span>本地部署 · 人工审核</span>
        </div>
      </section>
      <section class="login-form-area">
        <div class="login-form">
          <span class="login-icon"
            ><el-icon><Key /></el-icon
          ></span>
          <h2>登录工作台</h2>
          <p class="muted">开始处理今天的客户咨询</p>
          <el-form label-position="top" @submit.prevent="login"
            ><el-form-item label="账号"
              ><el-input
                v-model="username"
                autocomplete="username"
                placeholder="请输入账号"
                size="large" /></el-form-item
            ><el-form-item label="密码"
              ><el-input
                v-model="password"
                type="password"
                show-password
                autocomplete="current-password"
                placeholder="请输入密码"
                size="large" /></el-form-item
            ><el-button
              native-type="submit"
              type="primary"
              size="large"
              class="full-width"
              :loading="busy"
              :disabled="!username.trim() || !password"
              >进入工作台 <el-icon><ArrowRight /></el-icon></el-button
          ></el-form>
          <div class="login-note">
            <b>本地演示工作区</b>
            <p>
              可用账号：admin / supervisor / agent / knowledge<br />初始密码见项目
              .env 的 ADMIN_PASSWORD。
            </p>
          </div>
        </div>
      </section>
    </div>
    <div v-else class="shell">
      <button
        v-if="mobileNav"
        class="nav-scrim"
        aria-label="关闭导航"
        @click="mobileNav = false"
      ></button>
      <aside
        ref="sidebar"
        :inert="isMobile && !mobileNav"
        class="sidebar"
        :class="{ 'mobile-open': mobileNav }"
        aria-label="工作区导航"
      >
        <div class="sidebar-brand">
          <router-link
            class="brand"
            :to="navigation[0]?.path || '/tickets'"
            aria-label="TicketFlow 工作台"
            ><BrandMark /><span
              >TicketFlow<span class="brand-dot">.</span></span
            ></router-link
          ><button
            class="icon-button mobile-close"
            aria-label="关闭导航"
            @click="mobileNav = false"
          >
            <el-icon><Close /></el-icon>
          </button>
        </div>
        <div class="workspace-name">
          <span class="workspace-avatar">TF</span
          ><span><b>电商服务中心</b><small>本地工作区</small></span
          ><span class="workspace-status" aria-label="本地工作区"></span>
        </div>
        <nav aria-label="主导航">
          <router-link
            v-for="item in navigation"
            :key="item.path"
            :to="item.path"
            :aria-label="item.name"
            :aria-current="route.path === item.path ? 'page' : undefined"
            ><motion.span
              v-if="route.path === item.path"
              class="nav-selection"
              layout-id="workspace-navigation"
              :transition="{ type: 'spring', stiffness: 440, damping: 40 }"
              aria-hidden="true"
            /><el-icon aria-hidden="true"
              ><component :is="navIcons[item.icon]" /></el-icon
            ><span>{{ item.name }}</span></router-link
          >
        </nav>
        <div class="sidebar-bottom">
          <div class="human-note">
            <el-icon aria-hidden="true"><DocumentChecked /></el-icon
            ><span
              ><b>每次回复，由人确认</b
              ><small>AI 提供建议与可追溯证据</small></span
            >
          </div>
          <div class="sidebar-account">
            <span class="avatar">{{
              session.user.username[0].toUpperCase()
            }}</span
            ><span
              ><b>{{ session.user.username }}</b
              ><small>{{ roleNames[session.user.role] }}</small></span
            ><button
              type="button"
              class="icon-button"
              aria-label="退出登录"
              @click="logout"
            >
              <el-icon><SwitchButton /></el-icon>
            </button>
          </div>
        </div>
      </aside>
      <div class="main-shell" :inert="mobileNav">
        <header class="topbar">
          <div class="topbar-location">
            <button
              type="button"
              ref="menuButton"
              class="icon-button mobile-menu"
              aria-label="展开导航"
              :aria-expanded="mobileNav"
              @click="mobileNav = !mobileNav"
            >
              <el-icon><Menu /></el-icon>
            </button>
            <div class="breadcrumb">
              <span>工作空间</span><span class="breadcrumb-divider">/</span
              ><b>{{ active?.name || "工作台" }}</b>
            </div>
          </div>
          <div class="topbar-actions">
            <button
              type="button"
              class="global-search"
              aria-label="快捷搜索（Ctrl 或 Command 加 K）"
              @click="commandOpen = true"
            >
              <el-icon aria-hidden="true"><Search /></el-icon
              ><span>搜索页面、工单…</span><kbd>Ctrl K</kbd></button
            ><span
              v-if="system"
              class="service-state"
              :class="{ ready: system.llm_configured }"
              ><i></i
              >{{ system.llm_configured ? "模型已配置" : "模型待配置" }}</span
            ><span class="channel-chip">模拟客服渠道</span>
          </div>
        </header>
        <main id="main-content">
          <div
            v-if="system && !system.llm_configured"
            class="setup-banner"
            role="status"
          >
            <span>回复生成服务待配置，知识检索可正常使用。</span
            ><button type="button" @click="refreshStatus">重新检查</button>
          </div>
          <router-view v-slot="{ Component }"
            ><Transition name="page" mode="out-in"
              ><component :is="Component" :key="route.path" /></Transition
          ></router-view>
        </main>
        <footer>
          <span>TicketFlow · 智能客服协作</span
          ><span>本地工作区 · 回复经人工确认</span>
        </footer>
      </div>
      <CommandPalette v-model="commandOpen" @navigate="navigate" />
    </div>
  </MotionConfig>
</template>
