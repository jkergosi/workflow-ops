# Best Practices for Service Failure Handling

## Current Issues

1. **Supabase down** → Redirects to login page (bad UX)
2. **Backend service down** → Dashboard shows with no data (confusing)
3. **Database connection issues** → Same as backend down

**Goal:** Administrators need diagnostic info, but end users should see friendly messages without technical details.

---

## Recommended Solutions

### 1. Health Check System

Create a health check endpoint and frontend service:

**Backend:**
```python
# n8n-ops-backend/app/api/endpoints/health.py
@router.get("/health")
async def health_check():
    """Comprehensive health check"""
    checks = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {}
    }
    
    # Check database
    try:
        await db_service.client.table("users").select("id").limit(1).execute()
        checks["services"]["database"] = {"status": "healthy"}
    except Exception as e:
        checks["services"]["database"] = {"status": "unhealthy", "error": str(e)}
        checks["status"] = "degraded"
    
    # Check Supabase connection
    try:
        # Test Supabase connection
        checks["services"]["supabase"] = {"status": "healthy"}
    except Exception as e:
        checks["services"]["supabase"] = {"status": "unhealthy", "error": str(e)}
        checks["status"] = "degraded"
    
    status_code = 200 if checks["status"] == "healthy" else 503
    return JSONResponse(content=checks, status_code=status_code)
```

**Frontend Service:**
```typescript
// n8n-ops-ui/src/lib/health-service.ts
class HealthService {
  private status: 'healthy' | 'degraded' | 'unhealthy' = 'healthy';
  private listeners: Set<(status: string) => void> = new Set();
  
  async checkHealth(): Promise<HealthStatus> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/health`);
      const data = await response.json();
      this.status = data.status;
      this.notifyListeners();
      return data;
    } catch (error) {
      this.status = 'unhealthy';
      this.notifyListeners();
      return { status: 'unhealthy', services: {} };
    }
  }
  
  startPolling(interval = 30000) {
    setInterval(() => this.checkHealth(), interval);
  }
}
```

---

### 2. Service Status Indicator Component

Show status to admins, hide details from regular users:

```typescript
// n8n-ops-ui/src/components/ServiceStatusIndicator.tsx
export function ServiceStatusIndicator() {
  const { user } = useAuth();
  const { healthStatus } = useHealthCheck();
  const isAdmin = user?.role === 'admin';
  
  if (!isAdmin && healthStatus === 'healthy') return null;
  
  return (
    <div className="fixed bottom-4 right-4 z-50">
      {healthStatus === 'unhealthy' && (
        <Alert variant="destructive">
          <AlertTriangle />
          <AlertTitle>Service Unavailable</AlertTitle>
          <AlertDescription>
            {isAdmin ? (
              <ServiceDiagnostics status={healthStatus} />
            ) : (
              "We're experiencing technical difficulties. Please try again later."
            )}
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}
```

---

### 3. Error Boundaries with Graceful Degradation

```typescript
// n8n-ops-ui/src/components/ErrorBoundary.tsx
class ErrorBoundary extends React.Component {
  state = { hasError: false, error: null };
  
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  
  render() {
    if (this.state.hasError) {
      return <ErrorFallback error={this.state.error} />;
    }
    return this.props.children;
  }
}
```

---

### 4. Enhanced API Client with Retry Logic

```typescript
// Update api-client.ts interceptor
this.client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config;
    
    // Network errors - retry with backoff
    if (!error.response && error.code === 'ECONNABORTED') {
      if (!config._retryCount) config._retryCount = 0;
      if (config._retryCount < 3) {
        config._retryCount++;
        await new Promise(resolve => 
          setTimeout(resolve, Math.pow(2, config._retryCount) * 1000)
        );
        return this.client(config);
      }
    }
    
    // 503 Service Unavailable - show service status
    if (error.response?.status === 503) {
      // Trigger health check
      healthService.checkHealth();
      // Show user-friendly message
      throw new ServiceUnavailableError('Service temporarily unavailable');
    }
    
    // 401 - handle auth separately
    if (error.response?.status === 401) {
      // Only redirect if it's not a health check failure
      if (!config.url?.includes('/health')) {
        // Existing 401 handling
      }
    }
    
    return Promise.reject(error);
  }
);
```

---

### 5. Smart Empty States

Distinguish between "no data" and "service unavailable":

```typescript
// In EnvironmentsPage.tsx
const { data, error, isLoading } = useQuery({
  queryKey: ['environments'],
  queryFn: () => api.getEnvironments(),
  retry: (failureCount, error) => {
    // Don't retry on 503 - service is down
    if (error.response?.status === 503) return false;
    return failureCount < 2;
  }
});

if (error?.response?.status === 503) {
  return <ServiceUnavailableMessage isAdmin={user?.role === 'admin'} />;
}

if (error && !isLoading) {
  return <ErrorState error={error} isAdmin={user?.role === 'admin'} />;
}

if (!data?.data?.length && !isLoading) {
  return <EmptyState />; // Legitimate empty state
}
```

---

### 6. Admin Diagnostic Panel

```typescript
// n8n-ops-ui/src/components/AdminDiagnostics.tsx
export function AdminDiagnostics() {
  const { healthStatus, services } = useHealthCheck();
  
  if (!isAdmin) return null;
  
  return (
    <Card className="border-yellow-200 bg-yellow-50">
      <CardHeader>
        <CardTitle>System Diagnostics</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {Object.entries(services).map(([service, status]) => (
            <div key={service}>
              <Badge variant={status.status === 'healthy' ? 'default' : 'destructive'}>
                {service}: {status.status}
              </Badge>
              {status.error && (
                <p className="text-xs text-muted-foreground mt-1">
                  {status.error}
                </p>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
```

---

### 7. Connection Status Hook

```typescript
// n8n-ops-ui/src/lib/use-connection-status.ts
export function useConnectionStatus() {
  const [status, setStatus] = useState<'online' | 'offline' | 'degraded'>('online');
  
  useEffect(() => {
    const checkConnection = async () => {
      try {
        const response = await fetch('/api/v1/health', { 
          signal: AbortSignal.timeout(5000) 
        });
        const data = await response.json();
        setStatus(data.status === 'healthy' ? 'online' : 'degraded');
      } catch {
        setStatus('offline');
      }
    };
    
    checkConnection();
    const interval = setInterval(checkConnection, 30000);
    return () => clearInterval(interval);
  }, []);
  
  return status;
}
```

---

## Recommended Implementation Order

### Phase 1: Health Check System (Foundation)
- ✅ Backend health endpoint
- ✅ Frontend polling service
- ✅ Admin-only diagnostic panel

### Phase 2: Enhanced Error Handling
- ✅ Retry logic with exponential backoff
- ✅ Service-specific error messages
- ✅ Graceful degradation

### Phase 3: User Experience Improvements
- ✅ Connection status indicator
- ✅ Smart empty states
- ✅ Cached data fallback

### Phase 4: Advanced Features
- ✅ Error boundaries
- ✅ Offline mode detection
- ✅ Service recovery notifications

---

## Key Principles

1. **Fail Gracefully**: Show cached data or partial functionality when possible
2. **Inform Admins**: Detailed diagnostics for troubleshooting
3. **Protect Users**: Generic messages, no technical details
4. **Retry Intelligently**: Exponential backoff, don't retry on 503
5. **Monitor Proactively**: Health checks prevent surprises

---

## Error Handling Strategy Matrix

| Scenario | User Sees | Admin Sees | Action |
|----------|-----------|------------|--------|
| Supabase paused | "Service temporarily unavailable" | "Supabase connection failed: [error]" | Show admin diagnostics panel |
| Backend down | "Unable to connect. Please try again later" | "Backend service unreachable: [error]" | Retry with backoff, show status |
| Database timeout | "Loading is taking longer than expected" | "Database query timeout: [query]" | Retry once, then show error |
| Network error | "Connection lost. Retrying..." | "Network error: [details]" | Auto-retry with exponential backoff |
| 401 Unauthorized | Redirect to login | Same + "Auth token expired" | Clear token, redirect |
| 503 Service Unavailable | "Service maintenance in progress" | "Service degraded: [services]" | Show health status |

---

## Implementation Checklist

- [ ] Create `/api/v1/health` endpoint
- [ ] Create `HealthService` class
- [ ] Create `useHealthCheck` hook
- [ ] Create `ServiceStatusIndicator` component
- [ ] Create `AdminDiagnostics` component
- [ ] Update API client with retry logic
- [ ] Add error boundaries to App.tsx
- [ ] Update empty states to check service health
- [ ] Add connection status indicator to header
- [ ] Create user-friendly error messages
- [ ] Add admin-only diagnostic panel
- [ ] Implement cached data fallback
- [ ] Add service recovery notifications

