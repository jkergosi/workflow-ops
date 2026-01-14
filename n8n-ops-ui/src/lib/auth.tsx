import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import type { Session } from '@supabase/supabase-js';
import { supabase } from './supabase';
import { apiClient } from './api-client';
import { healthService } from './health-service';
import type { Entitlements } from '@/types';

interface User {
  id: string;
  email: string;
  name: string;
  role: 'admin' | 'developer' | 'viewer' | 'platform_admin';
  isPlatformAdmin?: boolean;
}

interface Tenant {
  id: string;
  name: string;
  subscriptionPlan: 'free' | 'pro' | 'agency' | 'agency_plus' | 'enterprise';
  createdAt?: string;
}

interface ActorUser {
  id: string;
  email: string;
  name?: string | null;
}

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  initComplete: boolean;
  needsOnboarding: boolean;
  backendUnavailable: boolean;
  user: User | null;
  tenant: Tenant | null;
  entitlements: Entitlements | null;
  session: Session | null;
  impersonating: boolean;
  actorUser: ActorUser | null;
  login: () => void;
  loginWithEmail: (email: string, password: string) => Promise<void>;
  loginWithOAuth: (provider: 'google' | 'github') => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  startImpersonation: (targetUserId: string) => Promise<void>;
  stopImpersonating: () => Promise<void>;
  completeOnboarding: (organizationName?: string) => Promise<void>;
  refreshEntitlements: () => Promise<void>;
  refreshAuth: () => Promise<void>;
  retryConnection: () => Promise<void>;
}


// Helper to check if error is a backend unavailability error
function isBackendUnavailableError(error: unknown): boolean {
  if (!error) return false;
  const err = error as any;
  // Check for service unavailable flag (set by api-client)
  if (err.isServiceUnavailable) return true;
  // Check for network error codes (covers various browsers/scenarios)
  if (err.code === 'ECONNABORTED' || err.code === 'ERR_NETWORK' ||
      err.code === 'ERR_CONNECTION_REFUSED' || err.code === 'ECONNREFUSED') return true;
  // Check for common network error messages
  if (err.message === 'Network Error') return true;
  if (err.message?.includes('timeout')) return true;
  if (err.message?.includes('CORS')) return true;
  if (err.message?.includes('Failed to fetch')) return true;
  // Check for 503 status
  if (err.response?.status === 503) return true;
  // CRITICAL: If there's a request but no response, the backend is likely unreachable
  // This is the ultimate fallback - any error where we sent a request but got no HTTP response
  if (err.request && !err.response) return true;
  return false;
}

// Keep a single context instance across Vite HMR updates.
// Without this, edits to this file can produce multiple live module copies (different `?t=`),
// causing providers/consumers to reference different contexts and crash at runtime.
const AUTH_CONTEXT_KEY = '__n8n_ops_auth_context__';
const AuthContext: React.Context<AuthContextType | undefined> =
  (globalThis as any)[AUTH_CONTEXT_KEY] ?? createContext<AuthContextType | undefined>(undefined);
if (import.meta.env.DEV) {
  (globalThis as any)[AUTH_CONTEXT_KEY] = AuthContext;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const isTest = import.meta.env.MODE === 'test';
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [entitlements, setEntitlements] = useState<Entitlements | null>(null);
  const [needsOnboarding, setNeedsOnboarding] = useState(false);
  const [impersonating, setImpersonating] = useState(false);
  const [actorUser, setActorUser] = useState<ActorUser | null>(null);
  const [authStatus, setAuthStatus] = useState<'initializing' | 'authenticated' | 'unauthenticated'>('initializing');
  const [backendUnavailable, setBackendUnavailable] = useState(false);

  // Track if we've already fetched user data to avoid duplicate calls
  const hasFetchedRef = useRef(false);

  const isLoading = authStatus === 'initializing';
  const initComplete = authStatus !== 'initializing';

  if (!isTest) {
    console.log('[Auth] Current state:', { authStatus, isLoading, initComplete, hasUser: !!user, hasTenant: !!tenant, impersonating, backendUnavailable });
  }

  // Fetch user data from backend after Supabase authentication
  const fetchUserData = useCallback(async (accessToken: string): Promise<{ success: boolean; backendDown?: boolean }> => {
    try {
      apiClient.setAuthToken(accessToken);

      const { data: statusData } = await apiClient.getAuthStatus();

      // Backend is reachable, clear any previous unavailable state
      setBackendUnavailable(false);

      if (statusData.onboarding_required) {
        setNeedsOnboarding(true);
        setUser(null);
        setTenant(null);
        setAuthStatus('authenticated');
        return { success: true };
      }

      if (statusData.user && statusData.tenant) {
        setUser({
          id: statusData.user.id,
          email: statusData.user.email,
          name: statusData.user.name,
          role: (statusData.user.role || 'viewer') as User['role'],
          isPlatformAdmin: !!(statusData.user as any)?.is_platform_admin,
        });
        setTenant({
          id: statusData.tenant.id,
          name: statusData.tenant.name,
          subscriptionPlan: (statusData.tenant.subscription_plan || 'free') as Tenant['subscriptionPlan'],
        });
        setNeedsOnboarding(false);

        setImpersonating(!!(statusData as any)?.impersonating);
        setActorUser(((statusData as any)?.actor_user as ActorUser) || null);

        if (statusData.entitlements) {
          setEntitlements(statusData.entitlements);
        }

        setAuthStatus('authenticated');
        return { success: true };
      } else {
        setAuthStatus('unauthenticated');
        return { success: false };
      }
    } catch (error) {
      if (!isTest) console.error('[Auth] Failed to fetch user data:', error);

      // Check if this is a backend unavailability error vs a real auth error
      if (isBackendUnavailableError(error)) {
        if (!isTest) console.warn('[Auth] Backend appears to be unavailable');
        setBackendUnavailable(true);
        // Don't set unauthenticated - the user might still be valid, just backend is down
        setAuthStatus('unauthenticated'); // Still need to complete init
        return { success: false, backendDown: true };
      }

      // Real auth error (like 401) - user is truly unauthenticated
      setBackendUnavailable(false);
      setAuthStatus('unauthenticated');
      return { success: false, backendDown: false };
    }
  }, [isTest]);

  // Initialize auth on mount
  useEffect(() => {
    const initAuth = async () => {
      try {
        // Get Supabase session
        const { data: { session: currentSession } } = await supabase.auth.getSession();

        if (currentSession) {
          setSession(currentSession);
        }

        if (currentSession) {
          hasFetchedRef.current = true;
          await fetchUserData(currentSession.access_token);
        } else {
          // No Supabase session - check if backend is available before assuming unauthenticated
          // This prevents redirect to login when backend is actually down
          let backendDown = false;
          try {
            const healthStatus = await healthService.checkHealth();
            if (!isTest) console.log('[Auth] Health check result:', healthStatus.status);
            if (healthStatus.status === 'unhealthy' || healthStatus.status === 'degraded') {
              if (!isTest) console.warn('[Auth] No session and backend is unavailable/degraded');
              backendDown = true;
            }
          } catch (healthError) {
            // Health check failed - backend is likely down
            if (!isTest) console.warn('[Auth] Health check failed, backend may be unavailable:', healthError);
            backendDown = true;
          }
          
          // Set backendUnavailable state if detected
          if (backendDown) {
            setBackendUnavailable(true);
          }
          setAuthStatus('unauthenticated');
        }
      } catch (error) {
        if (!isTest) console.error('[Auth] Failed to init auth:', error);
        // Check if backend is down
        if (isBackendUnavailableError(error)) {
          setBackendUnavailable(true);
        }
        setAuthStatus('unauthenticated');
      }
    };

    initAuth();

    // Listen for auth state changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, newSession) => {
        if (!isTest) console.log('[Auth] Auth state changed:', event);

        if (event === 'SIGNED_OUT') {
          hasFetchedRef.current = false; // Reset so next sign-in will fetch
          setSession(null);
          setUser(null);
          setTenant(null);
          setEntitlements(null);
          setImpersonating(false);
          setActorUser(null);
          setBackendUnavailable(false);
          setAuthStatus('unauthenticated');
          return;
        }

        if (newSession) {
          setSession(newSession);
          // Only fetch user data on actual sign-in events, not token refreshes or redundant initial events
          // Skip if we've already fetched (initAuth already handled it)
          const shouldFetch = !hasFetchedRef.current && event === 'SIGNED_IN';

          if (shouldFetch && !impersonating) {
            hasFetchedRef.current = true;
            await fetchUserData(newSession.access_token);
          }
        }
      }
    );

    return () => {
      subscription.unsubscribe();
    };
  }, [fetchUserData, isTest, impersonating]);

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
    setImpersonating(false);
    setActorUser(null);
    await supabase.auth.signOut();
  }, []);

  const startImpersonation = useCallback(async (targetUserId: string) => {
    try {
      if (!session?.access_token) {
        throw new Error('Not authenticated');
      }
      apiClient.setAuthToken(session.access_token);
      await apiClient.startPlatformImpersonation(targetUserId);
      window.location.reload();
    } catch (error) {
      if (!isTest) console.error('[Auth] Failed to start impersonation:', error);
      throw error;
    }
  }, [session?.access_token, isTest]);

  const stopImpersonating = useCallback(async () => {
    try {
      await apiClient.stopPlatformImpersonation();
    } catch {
      // Ignore error, just clear local state
    }

    setImpersonating(false);
    setActorUser(null);

    // Restore original session
    if (session) {
      apiClient.setAuthToken(session.access_token);
      await fetchUserData(session.access_token);
    }
    window.location.reload();
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

  const refreshAuth = useCallback(async () => {
    if (session) {
      await fetchUserData(session.access_token);
    }
  }, [session, fetchUserData]);

  
  // Retry connection when backend was unavailable
  const retryConnection = useCallback(async () => {
    if (!isTest) console.log('[Auth] Retrying connection...');
    setAuthStatus('initializing');

    if (session) {
      const result = await fetchUserData(session.access_token);
      if (result.success) {
        setBackendUnavailable(false);
      }
    } else {
      // Try to get a fresh session
      try {
        const { data: { session: currentSession } } = await supabase.auth.getSession();
        if (currentSession) {
          setSession(currentSession);
          const result = await fetchUserData(currentSession.access_token);
          if (result.success) {
            setBackendUnavailable(false);
          }
        } else {
          setAuthStatus('unauthenticated');
        }
      } catch (error) {
        if (!isTest) console.error('[Auth] Failed to retry connection:', error);
        setAuthStatus('unauthenticated');
      }
    }
  }, [session, fetchUserData, isTest]);

  const isAuthenticated = authStatus === 'authenticated';

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        isLoading,
        initComplete,
        needsOnboarding,
        backendUnavailable,
        user,
        tenant,
        entitlements,
        session,
        impersonating,
        actorUser,
        login,
        loginWithEmail,
        loginWithOAuth,
        signup,
        logout,
        startImpersonation,
        stopImpersonating,
        completeOnboarding,
        refreshEntitlements,
        refreshAuth,
        retryConnection,
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
