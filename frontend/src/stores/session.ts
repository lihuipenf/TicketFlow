import { defineStore } from "pinia";
import { ref } from "vue";
import { api, post } from "../api";
export const useSession = defineStore("session", () => {
  const user = ref<{ username: string; role: string; id: string } | null>(null);
  async function restore() {
    if (sessionStorage.getItem("ticketflow-token"))
      user.value = await api("/auth/me");
  }
  async function login(username: string, password: string) {
    const r = await post("/auth/login", { username, password });
    sessionStorage.setItem("ticketflow-token", r.access_token);
    user.value = r.user;
  }
  function logout() {
    sessionStorage.removeItem("ticketflow-token");
    user.value = null;
  }
  return { user, restore, login, logout };
});
