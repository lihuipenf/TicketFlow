import { createRouter, createWebHashHistory } from "vue-router";
export default createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/", redirect: "/tickets" },
    { path: "/tickets", component: () => import("./views/Tickets.vue") },
    { path: "/knowledge", component: () => import("./views/Knowledge.vue") },
    { path: "/workflow", component: () => import("./views/Workflow.vue") },
    { path: "/logs", component: () => import("./views/Logs.vue") },
    { path: "/orders", component: () => import("./views/Orders.vue") },
  ],
});
