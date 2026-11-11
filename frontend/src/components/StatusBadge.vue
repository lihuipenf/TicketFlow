<script setup lang="ts">
import { label } from "../api";
defineProps<{ status: string }>();
</script>
<template>
  <span class="status-badge" :class="'status-' + status">{{
    label(status)
  }}</span>
</template>
