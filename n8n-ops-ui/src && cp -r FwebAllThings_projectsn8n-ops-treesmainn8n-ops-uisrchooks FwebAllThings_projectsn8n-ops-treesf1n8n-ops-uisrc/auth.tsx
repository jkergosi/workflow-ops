import React, { createContext, useContext, useState, useEffect } from 'react';
import type { Tenant } from '@/types';

interface AuthContextType {
  isAuthenticated: boolean;
  user: Tenant | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  loading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState<Tenant | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check for existing auth token
    const token = localStorage.getItem('auth_token');
    if (token) {
      // Mock user for development
      const mockUser: Tenant = {
        id: '1',
        name: 'Demo Company',
        email: 'demo@example.com',
        subscriptionTier: 'free',
        createdAt: new Date().toISOString(),
        permissions: ['read', 'write', 'deploy'],
      };
      setUser(mockUser);
      setIsAuthenticated(true);
    }
    setLoading(false);
  }, []);

  const login = async (email: string, _password: string) => {
    setLoading(true);
    try {
      // Mock login - in production this would call Auth0
      await new Promise((resolve) => setTimeout(resolve, 500));

      const mockUser: Tenant = {
        id: '1',
        name: 'Demo Company',
        email,
        subscriptionTier: 'free',
        createdAt: new Date().toISOString(),
        permissions: ['read', 'write', 'deploy'],
      };

      localStorage.setItem('auth_token', 'mock_token_' + Date.now());
      setUser(mockUser);
      setIsAuthenticated(true);
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    localStorage.removeItem('auth_token');
    setUser(null);
    setIsAuthenticated(false);
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, user, login, logout, loading }}>
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
