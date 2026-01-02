import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import type { Session } from '@supabase/supabase-js';
import { supabase } from './supabase';
import { apiClient } from './api-client';
import type { Entitlements } from '@/types';

interface User {
  id: string;
  email: string;
  name: string;
  role: 'admin' | 'developer' | 'viewer';
}

interface Tenant {
  id: string;
  name: string;
  subscriptionPlan: 'free' | 'pro' | 'agency' | 'enterprise';
}

interface TenantUser {
  id: string;
  email: string;
  name: string;
  role: string;
  can_be_impersonated?: boolean;
}

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  initComplete: boolean;
  needsOnboarding: boolean;
  user: User | null;
  tenant: Tenant | null;
  entitlements: Entitlements | null;
  session: Session | null;
  impersonating: boolean;
  tenantUsers: TenantUser[];
  login: () => void;
  loginWithEmail: (email: string, password: string) => Promise<void>;
  loginWithOAuth: (provider: 'google' | 'github') => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  loginAs: (userId: string) => Promise<void>;
  stopImpersonating: () => Promise<void>;
  completeOnboarding: (organizationName?: string) => Promise<void>;
  refreshEntitlements: () => Promise<void>;
  refreshTenantUsers: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const isTest = import.meta.env.MODE === 'test';
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [entitlements, setEntitlements] = useState<Entitlements | null>(null);
  const [needsOnboarding, setNeedsOnboarding] = useState(false);
  const [tenantUsers, setTenantUsers] = useState<TenantUser[]>([]);
  const [impersonating, setImpersonating] = useState(false);
  const [authStatus, setAuthStatus] = useState<'initializing' | 'authenticated' | 'unauthenticated'>('initializing');

  const isLoading = authStatus === 'initializing';
  const initComplete = authStatus !== 'initializing';

  if (!isTest) {
    console.log('[Auth] Current state:', { authStatus, isLoading, initComplete, hasUser: !!user, hasTenant: !!tenant, impersonating });
  }

  // Fetch user data from backend after Supabase authentication
  const fetchUserData = useCallback(async (accessToken: string) => {
    try {
      apiClient.setAuthToken(accessToken);

      const { data: statusData } = await apiClient.getAuthStatus();

      if (statusData.onboarding_required) {
        setNeedsOnboarding(true);
        setUser(null);
        setTenant(null);
        setAuthStatus('authenticated');
        return;
      }

      if (statusData.user && statusData.tenant) {
        setUser({
          id: statusData.user.id,
          email: statusData.user.email,
          name: statusData.user.name,
          role: statusData.user.role || 'admin',
        });
        setTenant({
          id: statusData.tenant.id,
          name: statusData.tenant.name,
          subscriptionPlan: statusData.tenant.subscription_plan || 'free',
        });
        setNeedsOnboarding(false);

        if (statusData.entitlements) {
          setEntitlements(statusData.entitlements);
        }

        setAuthStatus('authenticated');
      } else {
        setAuthStatus('unauthenticated');
      }
    } catch (error) {
      if (!isTest) console.error('[Auth] Failed to fetch user data:', error);
      setAuthStatus('unauthenticated');
    }
  }, [isTest]);

  // Fetch tenant users for admin impersonation
  const refreshTenantUsers = useCallback(async () => {
    if (user?.role !== 'admin' || !tenant) {
      setTenantUsers([]);
      return;
    }

    try {
      const { data } = await apiClient.getTenantUsers();
      setTenantUsers(data.users || []);
    } catch (error) {
      if (!isTest) console.error('[Auth] Failed to fetch tenant users:', error);
      setTenantUsers([]);
    }
  }, [user?.role, tenant, isTest]);

  // Initialize auth on mount
  useEffect(() => {
    const initAuth = async () => {
      try {
        // Check for impersonation token first
        const impersonationToken = localStorage.getItem('impersonation_token');
        if (impersonationToken) {
          apiClient.setAuthToken(impersonationToken);
          setImpersonating(true);

          try {
            const { data: statusData } = await apiClient.getAuthStatus();
            if (statusData.user && statusData.tenant) {
              setUser({
                id: statusData.user.id,
                email: statusData.user.email,
                name: statusData.user.name,
                role: statusData.user.role || 'admin',
              });
              setTenant({
                id: statusData.tenant.id,
                name: statusData.tenant.name,
                subscriptionPlan: statusData.tenant.subscription_plan || 'free',
              });
              if (statusData.entitlements) {
                setEntitlements(statusData.entitlements);
              }
              setAuthStatus('authenticated');
              return;
            }
          } catch {
            // Impersonation token invalid, clear it
            localStorage.removeItem('impersonation_token');
            setImpersonating(false);
          }
        }

        // Get Supabase session
        const { data: { session: currentSession } } = await supabase.auth.getSession();

        if (currentSession) {
          setSession(currentSession);
          await fetchUserData(currentSession.access_token);
        } else {
          setAuthStatus('unauthenticated');
        }
      } catch (error) {
        if (!isTest) console.error('[Auth] Failed to init auth:', error);
        setAuthStatus('unauthenticated');
      }
    };

    initAuth();

    // Listen for auth state changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, newSession) => {
        if (!isTest) console.log('[Auth] Auth state changed:', event);

        if (event === 'SIGNED_OUT') {
          setSession(null);
          setUser(null);
          setTenant(null);
          setEntitlements(null);
          setTenantUsers([]);
          setImpersonating(false);
          localStorage.removeItem('impersonation_token');
          setAuthStatus('unauthenticated');
          return;
        }

        if (newSession) {
          setSession(newSession);
          // Don't fetch if impersonating
          if (!impersonating) {
            await fetchUserData(newSession.access_token);
          }
        }
      }
    );

    return () => {
      subscription.unsubscribe();
    };
  }, [fetchUserData, isTest, impersonating]);

  // Fetch tenant users when user/tenant changes
  useEffect(() => {
    if (user?.role === 'admin' && tenant && !impersonating) {
      refreshTenantUsers();
    }
  }, [user?.role, tenant, impersonating, refreshTenantUsers]);

  const login = useCallback(() => {
    window.location.href = '/login';
  }, []);

  const loginWithEmail = useCallback(async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) {
      throw error;
    }
  }, []);

  const loginWithOAuth = useCallback(async (provider: 'google' | 'github') => {
    const { error } = await supabase.auth.signInWithOAuth({
      provider,
      options: {
        redirectTo: `${window.location.origin}/login`
      }
    });
    if (error) {
      throw error;
    }
  }, []);

  const signup = useCallback(async (email: string, password: string) => {
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        emailRedirectTo: `${window.location.origin}/login`
      }
    });
    if (error) {
      throw error;
    }
  }, []);

  const logout = useCallback(async () => {
    localStorage.removeItem('impersonation_token');
    setImpersonating(false);
    await supabase.auth.signOut();
  }, []);

  const loginAs = useCallback(async (userId: string) => {
    try {
      const { data } = await apiClient.impersonateUser(userId);
      localStorage.setItem('impersonation_token', data.token);
      apiClient.setAuthToken(data.token);

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
      setImpersonating(true);

      // Refresh entitlements for impersonated user
      try {
        const { data: statusData } = await apiClient.getAuthStatus();
        if (statusData.entitlements) {
          setEntitlements(statusData.entitlements);
        }
      } catch {
        // Ignore entitlements fetch error
      }
    } catch (error) {
      if (!isTest) console.error('[Auth] Failed to impersonate user:', error);
      throw error;
    }
  }, [isTest]);

  const stopImpersonating = useCallback(async () => {
    try {
      await apiClient.stopImpersonating();
    } catch {
      // Ignore error, just clear local state
    }

    localStorage.removeItem('impersonation_token');
    setImpersonating(false);

    // Restore original session
    if (session) {
      apiClient.setAuthToken(session.access_token);
      await fetchUserData(session.access_token);
    }
  }, [session, fetchUserData]);

  const completeOnboarding = useCallback(async (organizationName?: string) => {
    try {
      await apiClient.completeOnboarding({ organization_name: organizationName });
      setNeedsOnboarding(false);

      // Refresh user data
      if (session) {
        await fetchUserData(session.access_token);
      }
    } catch (error) {
      if (!isTest) console.error('[Auth] Failed to complete onboarding:', error);
      throw error;
    }
  }, [session, fetchUserData, isTest]);

  const refreshEntitlements = useCallback(async () => {
    try {
      const { data } = await apiClient.getAuthStatus();
      if (data.entitlements) {
        setEntitlements(data.entitlements);
      }
    } catch (error) {
      if (!isTest) console.error('[Auth] Failed to refresh entitlements:', error);
    }
  }, [isTest]);

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
        session,
        impersonating,
        tenantUsers,
        login,
        loginWithEmail,
        loginWithOAuth,
        signup,
        logout,
        loginAs,
        stopImpersonating,
        completeOnboarding,
        refreshEntitlements,
        refreshTenantUsers,
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
