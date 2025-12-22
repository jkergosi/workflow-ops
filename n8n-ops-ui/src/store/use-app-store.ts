import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { EnvironmentType } from '@/types';

interface AppState {
  // selectedEnvironment can now be either an environment ID (preferred) or type string (for backward compatibility)
  selectedEnvironment: EnvironmentType;
  setSelectedEnvironment: (env: EnvironmentType) => void;

  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;

  theme: 'light' | 'dark';
  setTheme: (theme: 'light' | 'dark') => void;
  toggleTheme: () => void;

  // Provider state
  selectedProvider: string;
  setSelectedProvider: (providerId: string) => void;
  providerDisplayName: string;
  setProviderDisplayName: (name: string) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      selectedEnvironment: 'dev',
      setSelectedEnvironment: (env) => set({ selectedEnvironment: env }),

      sidebarOpen: true,
      setSidebarOpen: (open) => set({ sidebarOpen: open }),
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),

      theme: 'light',
      setTheme: (theme) => set({ theme }),
      toggleTheme: () => set((state) => ({ theme: state.theme === 'light' ? 'dark' : 'light' })),

      // Provider state
      selectedProvider: 'n8n',
      setSelectedProvider: (providerId) => set({ selectedProvider: providerId }),
      providerDisplayName: 'n8n',
      setProviderDisplayName: (name) => set({ providerDisplayName: name }),
    }),
    {
      name: 'n8n-ops-store',
      partialize: (state) => ({
        selectedProvider: state.selectedProvider,
        providerDisplayName: state.providerDisplayName,
      }),
    }
  )
);
