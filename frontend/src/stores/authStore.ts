import { create } from "zustand";

interface AuthState {
  token: string | null;
  userId: string | null;
  name: string | null;
  role: string | null;
  isAuthenticated: boolean;

  login: (token: string, userId: string, name: string, role: string) => void;
  logout: () => void;
  loadFromStorage: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  userId: null,
  name: null,
  role: null,
  isAuthenticated: false,

  login: (token, userId, name, role) => {
    localStorage.setItem("auth_token", token);
    localStorage.setItem("auth_user", JSON.stringify({ userId, name, role }));
    set({ token, userId, name, role, isAuthenticated: true });
  },

  logout: () => {
    localStorage.removeItem("auth_token");
    localStorage.removeItem("auth_user");
    set({ token: null, userId: null, name: null, role: null, isAuthenticated: false });
  },

  loadFromStorage: () => {
    const token = localStorage.getItem("auth_token");
    const userStr = localStorage.getItem("auth_user");
    if (token && userStr) {
      try {
        const user = JSON.parse(userStr);
        set({
          token,
          userId: user.userId,
          name: user.name,
          role: user.role,
          isAuthenticated: true,
        });
      } catch {
        // Corrupted storage, clear it
        localStorage.removeItem("auth_token");
        localStorage.removeItem("auth_user");
      }
    }
  },
}));
