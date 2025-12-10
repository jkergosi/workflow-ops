import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { apiClient } from './api-client';

// Dev mode - bypass Auth0 entirely
const DEV_MODE = import.meta.env.VITE_USE_MOCK_AUTH === 'true' || true; // Force dev mode for now

interface User {
  id: string;
  email: string;
  name: string;
  role: 'admin' | 'developer' | 'viewer';
}

interface Tenant {
  id: string;
  name: string;
  subscriptionPlan: 'free' | 'pro' | 'enterprise';
}

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  needsOnboarding: boolean;
  user: User | null;
  tenant: Tenant | null;
  availableUsers: Array<{ id: string; email: string; name: string; tenant_id: string }>;
  login: () => void;
  logout: () => void;
  loginAs: (userId: string) => Promise<void>;
  completeOnboarding: (organizationName?: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [needsOnboarding, setNeedsOnboarding] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [availableUsers, setAvailableUsers] = useState<Array<{ id: string; email: string; name: string; tenant_id: string }>>([]);

  // Load available users and auto-login on mount
  useEffect(() => {
    const initAuth = async () => {
      try {
        // Get list of users from backend
        const { data } = await apiClient.getDevUsers();
        setAvailableUsers(data.users || []);

        // Check if we have a saved user in localStorage
        const savedUserId = localStorage.getItem('dev_user_id');
        if (savedUserId && data.users?.length > 0) {
          const savedUser = data.users.find((u: { id: string }) => u.id === savedUserId);
          if (savedUser) {
            await loginAsUser(savedUser.id);
            return;
          }
        }

        // Auto-login as first user if available
        if (data.users && data.users.length > 0) {
          await loginAsUser(data.users[0].id);
        } else {
          // No users exist - need onboarding
          setNeedsOnboarding(true);
        }
      } catch (error) {
        console.error('Failed to init auth:', error);
        setNeedsOnboarding(true);
      } finally {
        setIsLoading(false);
      }
    };

    if (DEV_MODE) {
      initAuth();
    }
  }, []);

  const loginAsUser = async (userId: string) => {
    try {
      setIsLoading(true);
      const { data } = await apiClient.devLoginAs(userId);

      if (data.user && data.tenant) {
        setUser({
          id: data.user.id,
          email: data.user.email,
          name: data.user.name,
          role: data.user.role,
        });
        setTenant({
          id: data.tenant.id,
          name: data.tenant.name,
          subscriptionPlan: data.tenant.subscription_tier || 'free',
        });
        setNeedsOnboarding(false);
        localStorage.setItem('dev_user_id', userId);
        // Set a mock token for API calls
        apiClient.setAuthToken(`dev-token-${userId}`);
      }
    } catch (error) {
      console.error('Failed to login as user:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const login = useCallback(() => {
    // In dev mode, just reload to trigger auto-login
    window.location.reload();
  }, []);

  const logout = useCallback(() => {
    apiClient.setAuthToken(null);
    setUser(null);
    setTenant(null);
    setNeedsOnboarding(false);
    localStorage.removeItem('dev_user_id');
  }, []);

  const loginAs = useCallback(async (userId: string) => {
    await loginAsUser(userId);
  }, []);

  const completeOnboarding = useCallback(async (organizationName?: string) => {
    try {
      const { data } = await apiClient.devCreateUser(organizationName);

      if (data.user && data.tenant) {
        setUser({
          id: data.user.id,
          email: data.user.email,
          name: data.user.name,
          role: data.user.role,
        });
        setTenant({
          id: data.tenant.id,
          name: data.tenant.name,
          subscriptionPlan: data.tenant.subscription_tier || 'free',
        });
        setNeedsOnboarding(false);
        localStorage.setItem('dev_user_id', data.user.id);
        apiClient.setAuthToken(`dev-token-${data.user.id}`);

        // Refresh available users
        const usersResponse = await apiClient.getDevUsers();
        setAvailableUsers(usersResponse.data.users || []);
      }
    } catch (error) {
      console.error('Failed to complete onboarding:', error);
      throw error;
    }
  }, []);

  const isAuthenticated = user !== null && tenant !== null;

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        isLoading,
        needsOnboarding,
        user,
        tenant,
        availableUsers,
        login,
        logout,
        loginAs,
        completeOnboarding,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
