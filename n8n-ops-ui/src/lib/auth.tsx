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
  initComplete: boolean;
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
  const [availableUsers, setAvailableUsers] = useState<Array<{ id: string; email: string; name: string; tenant_id: string }>>([]);
  // Use a single status to avoid race conditions between multiple state variables
  const [authStatus, setAuthStatus] = useState<'initializing' | 'authenticated' | 'unauthenticated'>('initializing');

  // Derived values for backwards compatibility
  const isLoading = authStatus === 'initializing';
  const initComplete = authStatus !== 'initializing';

  // Debug logging
  console.log('[Auth] Current state:', { authStatus, isLoading, initComplete, hasUser: !!user, hasTenant: !!tenant });

  // Load available users and auto-login on mount
  useEffect(() => {
    const initAuth = async () => {
      try {
        // Get list of users from backend (no auth required for this endpoint)
        const { data } = await apiClient.getDevUsers();
        const users = data.users || [];
        setAvailableUsers(users);

        if (users.length > 0) {
          // Check if we have a saved user ID, otherwise use first user
          const savedUserId = localStorage.getItem('dev_user_id');
          const userIdToUse = savedUserId && users.find(u => u.id === savedUserId)
            ? savedUserId
            : users[0].id;

          const selectedUser = users.find(u => u.id === userIdToUse) || users[0];

          // Set the token BEFORE making the login call
          const devToken = `dev-token-${selectedUser.id}`;
          apiClient.setAuthToken(devToken);
          localStorage.setItem('dev_user_id', selectedUser.id);

          try {
            const loginResult = await apiClient.devLoginAs(selectedUser.id);
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

              // Fetch entitlements after login
              try {
                const { data: statusData } = await apiClient.getAuthStatus();
                if (statusData.entitlements) {
                  console.log('[Auth] Loaded entitlements:', statusData.entitlements);
                  setEntitlements(statusData.entitlements);
                } else {
                  console.warn('[Auth] No entitlements in status response');
                }
              } catch (entitlementError) {
                console.warn('Failed to fetch entitlements:', entitlementError);
              }

              // Mark as authenticated after all state is set
              setAuthStatus('authenticated');
            } else {
              // No user/tenant data returned
              console.warn('[Auth] No user or tenant data in login response');
              setAuthStatus('unauthenticated');
            }
          } catch (loginError) {
            console.error('Failed to login as user:', loginError);
            // Even if login fails, try to set user from what we know
            // But also set a dummy tenant to allow dev mode to work
            setUser({
              id: selectedUser.id,
              email: selectedUser.email,
              name: selectedUser.name,
              role: 'admin',
            });
            setTenant({
              id: 'dev-tenant',
              name: 'Development',
              subscriptionPlan: 'enterprise',
            });
            setNeedsOnboarding(false);
            setAuthStatus('authenticated');
          }
        } else {
          // No users exist
          console.log('No users in database');
          setNeedsOnboarding(false);
          setAuthStatus('unauthenticated');
        }
      } catch (error) {
        console.error('Failed to init auth:', error);
        setNeedsOnboarding(false);
        setAuthStatus('unauthenticated');
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
      setAuthStatus('initializing');
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
        setAuthStatus('authenticated');
      } else {
        setAuthStatus('unauthenticated');
      }
    } catch (error) {
      console.error('Failed to login as user:', error);
      setAuthStatus('unauthenticated');
    }
  }, []);

  const completeOnboarding = useCallback(async (_organizationName?: string) => {
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

  // Use the authStatus directly - this is the single source of truth
  const isAuthenticated = authStatus === 'authenticated';

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        isLoading,
        initComplete,
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
