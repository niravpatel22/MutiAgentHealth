import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { apiRequest, clearAccessToken, refreshSession, setAccessToken } from '../../api/client.js';

const AuthContext = createContext(null);

export function AuthProvider({ children, initialUser = null, skipBootstrap = false }) {
  const [user, setUser] = useState(initialUser);
  const [isLoading, setIsLoading] = useState(!skipBootstrap && !initialUser);
  const [activeDatasetId, setActiveDatasetId] = useState(null);
  const [theme, setTheme] = useState('light');
  const [toasts, setToasts] = useState([]);

  const notify = useCallback((message, tone = 'info') => {
    const id = `${Date.now()}-${Math.random()}`;
    setToasts((prev) => [...prev, { id, message, tone }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  useEffect(() => {
    if (skipBootstrap || initialUser) return;
    let active = true;
    (async () => {
      const refreshed = await refreshSession();
      let resolvedUser = refreshed?.user ?? null;
      if (!resolvedUser && refreshed?.access_token) {
        // Cookie refresh unavailable: validate the tab-scoped token against /auth/me instead.
        try {
          resolvedUser = await apiRequest('/auth/me', { skipAuthRefresh: true });
        } catch {
          clearAccessToken();
          resolvedUser = null;
        }
      }
      if (active) {
        setUser(resolvedUser);
        setIsLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [skipBootstrap, initialUser]);

  const login = useCallback(
    async (email, password) => {
      const data = await apiRequest('/auth/login', {
        method: 'POST',
        body: { email, password },
        skipAuthRefresh: true,
      });
      setAccessToken(data.access_token);
      setUser(data.user);
      notify(`Signed in as ${data.user.email}`, 'success');
      return data.user;
    },
    [notify],
  );

  const register = useCallback(
    async (email, password) => {
      const created = await apiRequest('/auth/register', {
        method: 'POST',
        body: { email, password },
        skipAuthRefresh: true,
      });
      notify('Account created. Signing you in…', 'success');
      await login(email, password);
      return created;
    },
    [login, notify],
  );

  const logout = useCallback(async () => {
    try {
      await apiRequest('/auth/logout', { method: 'POST', skipAuthRefresh: true });
    } finally {
      clearAccessToken();
      setUser(null);
      setActiveDatasetId(null);
    }
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme((prev) => (prev === 'light' ? 'dark' : 'light'));
  }, []);

  const value = useMemo(
    () => ({
      user,
      setUser,
      isLoading,
      login,
      register,
      logout,
      activeDatasetId,
      setActiveDatasetId,
      theme,
      toggleTheme,
      toasts,
      notify,
    }),
    [user, isLoading, login, register, logout, activeDatasetId, theme, toggleTheme, toasts, notify],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used inside <AuthProvider>');
  }
  return ctx;
}
