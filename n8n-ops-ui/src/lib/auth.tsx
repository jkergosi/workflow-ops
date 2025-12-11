import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { apiClient } from './api-client';
import type { Entitlements } from '@/types';

// DEV MODE - Always enabled, bypasses Auth0 entirely
// Assumes first user in database is the current user

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
  entitlements: Entitlements | null;
  availableUsers: Array<{ id: string; email: string; name: string; tenant_id: string }>;
  login: () => void;
  logout: () => void;
  loginAs: (userId: string) => Promise<void>;
  completeOnboarding: (organizationName?: string) => Promise<void>;
  refreshEntitlements: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [entitlements, setEntitlements] = useState<Entitlements | null>(null);
  const [needsOnboarding, setNeedsOnboarding] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [availableUsers, setAvailableUsers] = useState<Array<{ id: string; email: string; name: string; tenant_id: string }>>([]);

  // Load available users and auto-login on mount
  useEffect(() => {
    const initAuth = async () => {
      try {
        // Get list of users from backend
        try {
          const { data } = await apiClient.getDevUsers();
          const users = data.users || [];
          setAvailableUsers(users);

        if (users.length > 0) {
          // Auto-login as first user
          const firstUser = users[0];
          try {
            const loginResult = await apiClient.devLoginAs(firstUser.id);
            if (loginResult.data.user && loginResult.data.tenant) {
              setUser({
                id: loginResult.data.user.id,
                email: loginResult.data.user.email,
                name: loginResult.data.user.name,
                role: loginResult.data.user.role || 'admin',
              });
              setTenant({
                id: loginResult.data.tenant.id,
                name: loginResult.data.tenant.name,
                subscriptionPlan: loginResult.data.tenant.subscription_tier || 'free',
              });
              setNeedsOnboarding(false);
              localStorage.setItem('dev_user_id', firstUser.id);
              apiClient.setAuthToken(`dev-token-${firstUser.id}`);

              // Fetch entitlements after login
              try {
                const { data: statusData } = await apiClient.getAuthStatus();
                if (statusData.entitlements) {
                  setEntitlements(statusData.entitlements);
                }
              } catch (entitlementError) {
                console.warn('Failed to fetch entitlements:', entitlementError);
              }
            }
          } catch (loginError) {
            console.error('Failed to login as first user:', loginError);
            // Still don't need onboarding if users exist
            setNeedsOnboarding(false);
          }
        } else {
          // No users exist - but don't require onboarding, just skip auth
          console.log('No users in database - running without authentication');
          setNeedsOnboarding(false);
          // Set a dummy user/tenant so the app works
          setUser({
            id: 'dev-user',
            email: 'dev@example.com',
            name: 'Dev User',
            role: 'admin',
          });
          setTenant({
            id: 'dev-tenant',
            name: 'Dev Tenant',
            subscriptionPlan: 'enterprise',
          });
        }
        } catch (authError) {
          // If auth endpoint fails (404), continue without auth (dev mode)
          console.warn('Auth endpoint not available, continuing without authentication:', authError);
          setNeedsOnboarding(false);
          setUser({
            id: 'dev-user',
            email: 'dev@example.com',
            name: 'Dev User',
            role: 'admin',
          });
          setTenant({
            id: 'dev-tenant',
            name: 'Dev Tenant',
            subscriptionPlan: 'enterprise',
          });
        }
      } catch (error) {
        console.error('Failed to init auth:', error);
        // On error, skip auth and use dummy user
        setNeedsOnboarding(false);
        setUser({
          id: 'dev-user',
          email: 'dev@example.com',
          name: 'Dev User',
          role: 'admin',
        });
        setTenant({
          id: 'dev-tenant',
          name: 'Dev Tenant',
          subscriptionPlan: 'enterprise',
        });
      } finally {
        setIsLoading(false);
      }
    };

    initAuth();
  }, []);

  const login = useCallback(() => {
    window.location.reload();
  }, []);

  const logout = useCallback(() => {
    apiClient.setAuthToken(null);
    localStorage.removeItem('dev_user_id');
    window.location.reload();
  }, []);

  const loginAs = useCallback(async (userId: string) => {
    try {
      setIsLoading(true);
      const { data } = await apiClient.devLoginAs(userId);
      if (data.user && data.tenant) {
        setUser({
          id: data.user.id,
          email: data.user.email,
          name: data.user.name,
          role: data.user.role || 'admin',
        });
        setTenant({
          id: data.tenant.id,
          name: data.tenant.name,
          subscriptionPlan: data.tenant.subscription_tier || 'free',
        });
        localStorage.setItem('dev_user_id', userId);
        apiClient.setAuthToken(`dev-token-${userId}`);

        // Fetch entitlements after switching users
        try {
          const { data: statusData } = await apiClient.getAuthStatus();
          if (statusData.entitlements) {
            setEntitlements(statusData.entitlements);
          }
        } catch (entitlementError) {
          console.warn('Failed to fetch entitlements:', entitlementError);
        }
      }
    } catch (error) {
      console.error('Failed to login as user:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const completeOnboarding = useCallback(async (organizationName?: string) => {
    // No-op in dev mode - onboarding is disabled
    setNeedsOnboarding(false);
  }, []);

  const refreshEntitlements = useCallback(async () => {
    try {
      const { data } = await apiClient.getAuthStatus();
      if (data.entitlements) {
        setEntitlements(data.entitlements);
      }
    } catch (error) {
      console.error('Failed to refresh entitlements:', error);
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
        entitlements,
        availableUsers,
        login,
        logout,
        loginAs,
        completeOnboarding,
        refreshEntitlements,
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
