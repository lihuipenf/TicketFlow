<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { Search } from "@element-plus/icons-vue";
import { api } from "../api";
import StatusBadge from "../components/StatusBadge.vue";
const orders = ref<any[]>([]),
  query = ref(""),
  loading = ref(false);
async function load() {
  loading.value = true;
  try {
    orders.value = await api("/orders?q=" + encodeURIComponent(query.value));
  } catch (e) {
    ElMessage.error((e as Error).message);
  } finally {
    loading.value = false;
  }
}
onMounted(load);
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>模拟订单</h1>
      <p>50 条关联订单，覆盖支付、物流和售后状态。</p>
    </div>
    <span class="channel-chip">只读业务工具</span>
  </div>
  <section class="panel">
    <div class="panel-head">
      <h3>
        订单列表 <span class="counter">{{ orders.length }}</span>
      </h3>
      <span class="subtle">合成数据 · 不涉及真实交易</span>
    </div>
    <div class="toolbar">
      <el-input
        v-model="query"
        aria-label="搜索订单"
        :prefix-icon="Search"
        placeholder="订单编号或客户编号"
        clearable
        @keyup.enter="load"
        @clear="load"
      /><el-button @click="load">查询订单</el-button>
    </div>
    <el-table :data="orders" v-loading="loading"
      ><el-table-column
        prop="id"
        label="订单编号"
        min-width="160"
      /><el-table-column
        prop="customer_id"
        label="客户"
        width="100"
      /><el-table-column
        prop="product"
        label="商品"
        min-width="180"
      /><el-table-column label="订单金额" width="130"
        ><template #default="{ row }"
          >¥ {{ (row.amount_cents / 100).toFixed(2) }}</template
        ></el-table-column
      ><el-table-column label="实时状态" width="140"
        ><template #default="{ row }"
          ><StatusBadge :status="row.status" /></template></el-table-column
      ><el-table-column label="物流" min-width="120"
        ><template #default="{ row }">{{
          row.facts.shipping_carrier || "—"
        }}</template></el-table-column
      ></el-table
    >
  </section>
</template>
