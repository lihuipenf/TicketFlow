<script setup lang="ts">
import { onMounted, onUnmounted, watch, ref } from "vue";
import * as echarts from "echarts/core";
import { BarChart, PieChart } from "echarts/charts";
import {
  TooltipComponent,
  GridComponent,
  LegendComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
echarts.use([
  BarChart,
  PieChart,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  CanvasRenderer,
]);
const props = defineProps<{ data: Record<string, number>; type?: string }>(),
  target = ref<HTMLElement | null>(null);
let chart: echarts.ECharts, observer: ResizeObserver;
function render() {
  if (!chart) return;
  const entries = Object.entries(props.data);
  chart.setOption(
    {
      animation: !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
      ...(props.type === "pie"
        ? {
            color: [
              "#329273",
              "#92c6a4",
              "#d5bf8b",
              "#6e95b2",
              "#b7a4c5",
              "#cbd5cf",
            ],
            tooltip: { trigger: "item" },
            legend: {
              bottom: 8,
              textStyle: { color: "#52635e", fontSize: 11 },
            },
            series: [
              {
                type: "pie",
                radius: ["48%", "70%"],
                center: ["50%", "44%"],
                itemStyle: {
                  borderRadius: 5,
                  borderColor: "#fff",
                  borderWidth: 4,
                },
                label: { show: false },
                data: entries.map(([name, value]) => ({ name, value })),
              },
            ],
          }
        : {
            grid: { left: 45, right: 18, bottom: 55, top: 25 },
            tooltip: { trigger: "axis" },
            xAxis: {
              type: "category",
              data: entries.map((e) => e[0]),
              axisLabel: {
                color: "#52635e",
                fontSize: 11,
                interval: 0,
                rotate: 20,
              },
              axisTick: { show: false },
              axisLine: { lineStyle: { color: "#e7eee8" } },
            },
            yAxis: {
              type: "value",
              splitLine: { lineStyle: { color: "#f0f3f0" } },
              axisLabel: { color: "#64756f", fontSize: 11 },
            },
            series: [
              {
                type: "bar",
                data: entries.map((e) => e[1]),
                barMaxWidth: 28,
                itemStyle: { color: "#3a8b6b", borderRadius: [4, 4, 0, 0] },
              },
            ],
          }),
    },
    true,
  );
}
onMounted(() => {
  chart = echarts.init(target.value!);
  render();
  observer = new ResizeObserver(() => chart.resize());
  observer.observe(target.value!);
});
watch(() => props.data, render, { deep: true });
onUnmounted(() => {
  observer?.disconnect();
  chart?.dispose();
});
</script>
<template>
  <div
    ref="target"
    class="chart"
    role="img"
    :aria-label="JSON.stringify(data)"
  ></div>
</template>
