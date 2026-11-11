<script setup lang="ts">
import { motion } from "motion-v";
defineProps<{
  modelValue: string;
  items: { value: string; label: string; count?: number }[];
}>();
const emit = defineEmits<{ "update:modelValue": [value: string] }>();
</script>
<template>
  <div class="status-tabs" role="group" aria-label="按工单状态筛选">
    <button
      v-for="item in items"
      :key="item.value"
      type="button"
      class="status-tab"
      :class="{ selected: modelValue === item.value }"
      :aria-pressed="modelValue === item.value"
      @click="emit('update:modelValue', item.value)"
    >
      <motion.span
        v-if="modelValue === item.value"
        class="tab-selection"
        layout-id="queue-selection"
        :transition="{ type: 'spring', stiffness: 440, damping: 38 }"
        aria-hidden="true"
      />
      <span>{{ item.label }}</span
      ><span v-if="item.count !== undefined" class="tab-count">{{
        item.count
      }}</span>
    </button>
  </div>
</template>
