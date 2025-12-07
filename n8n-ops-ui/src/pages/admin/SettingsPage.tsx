import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import {
  Settings,
  Database,
  Mail,
  Key,
  Save,
  RefreshCw,
  CheckCircle,
  AlertTriangle,
} from 'lucide-react';
import { toast } from 'sonner';

interface SystemConfig {
  appName: string;
  appUrl: string;
  supportEmail: string;
  defaultTimezone: string;
  maintenanceMode: boolean;
}

interface DatabaseConfig {
  host: string;
  port: number;
  database: string;
  connectionPoolSize: number;
  status: 'connected' | 'disconnected' | 'error';
}

interface EmailConfig {
  smtpHost: string;
  smtpPort: number;
  smtpUser: string;
  fromName: string;
  fromEmail: string;
}

const mockSystemConfig: SystemConfig = {
  appName: 'N8N Ops',
  appUrl: 'https://app.n8nops.com',
  supportEmail: 'support@n8nops.com',
  defaultTimezone: 'UTC',
  maintenanceMode: false,
};

const mockDatabaseConfig: DatabaseConfig = {
  host: 'db.supabase.co',
  port: 5432,
  database: 'n8n_ops',
  connectionPoolSize: 20,
  status: 'connected',
};

const mockEmailConfig: EmailConfig = {
  smtpHost: 'smtp.sendgrid.net',
  smtpPort: 587,
  smtpUser: 'apikey',
  fromName: 'N8N Ops',
  fromEmail: 'noreply@n8nops.com',
};

export function SettingsPage() {
  const [systemConfig, setSystemConfig] = useState(mockSystemConfig);
  const [emailConfig, setEmailConfig] = useState(mockEmailConfig);
  const [isSaving, setIsSaving] = useState(false);

  const handleSaveSystem = async () => {
    setIsSaving(true);
    // Simulate API call
    await new Promise((resolve) => setTimeout(resolve, 1000));
    setIsSaving(false);
    toast.success('System settings saved successfully');
  };

  const handleSaveEmail = async () => {
    setIsSaving(true);
    await new Promise((resolve) => setTimeout(resolve, 1000));
    setIsSaving(false);
    toast.success('Email settings saved successfully');
  };

  const handleTestEmail = async () => {
    toast.info('Sending test email...');
    await new Promise((resolve) => setTimeout(resolve, 2000));
    toast.success('Test email sent successfully');
  };

  const handleTestDatabase = async () => {
    toast.info('Testing database connection...');
    await new Promise((resolve) => setTimeout(resolve, 1500));
    toast.success('Database connection successful');
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="text-muted-foreground">Configure system-wide settings and integrations</p>
      </div>

      <div className="grid gap-6">
        {/* System Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Settings className="h-5 w-5" />
              System Settings
            </CardTitle>
            <CardDescription>General application configuration</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="app-name">Application Name</Label>
                <Input
                  id="app-name"
                  value={systemConfig.appName}
                  onChange={(e) =>
                    setSystemConfig({ ...systemConfig, appName: e.target.value })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="app-url">Application URL</Label>
                <Input
                  id="app-url"
                  value={systemConfig.appUrl}
                  onChange={(e) =>
                    setSystemConfig({ ...systemConfig, appUrl: e.target.value })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="support-email">Support Email</Label>
                <Input
                  id="support-email"
                  type="email"
                  value={systemConfig.supportEmail}
                  onChange={(e) =>
                    setSystemConfig({ ...systemConfig, supportEmail: e.target.value })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="timezone">Default Timezone</Label>
                <select
                  id="timezone"
                  value={systemConfig.defaultTimezone}
                  onChange={(e) =>
                    setSystemConfig({ ...systemConfig, defaultTimezone: e.target.value })
                  }
                  className="flex h-9 w-full rounded-md border border-input bg-background text-foreground px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                >
                  <option value="UTC">UTC</option>
                  <option value="America/New_York">Eastern Time</option>
                  <option value="America/Chicago">Central Time</option>
                  <option value="America/Denver">Mountain Time</option>
                  <option value="America/Los_Angeles">Pacific Time</option>
                  <option value="Europe/London">London</option>
                  <option value="Europe/Paris">Paris</option>
                  <option value="Asia/Tokyo">Tokyo</option>
                </select>
              </div>
            </div>

            <div className="flex items-center justify-between p-4 rounded-lg border">
              <div>
                <p className="font-medium">Maintenance Mode</p>
                <p className="text-sm text-muted-foreground">
                  When enabled, users will see a maintenance page
                </p>
              </div>
              <Button
                variant={systemConfig.maintenanceMode ? 'destructive' : 'outline'}
                onClick={() =>
                  setSystemConfig({
                    ...systemConfig,
                    maintenanceMode: !systemConfig.maintenanceMode,
                  })
                }
              >
                {systemConfig.maintenanceMode ? 'Disable' : 'Enable'}
              </Button>
            </div>

            <div className="flex justify-end">
              <Button onClick={handleSaveSystem} disabled={isSaving}>
                <Save className="h-4 w-4 mr-2" />
                {isSaving ? 'Saving...' : 'Save Changes'}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Database Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5" />
              Database Connection
            </CardTitle>
            <CardDescription>PostgreSQL database configuration</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between p-4 rounded-lg bg-muted/50">
              <div className="flex items-center gap-3">
                {mockDatabaseConfig.status === 'connected' ? (
                  <CheckCircle className="h-5 w-5 text-green-500" />
                ) : (
                  <AlertTriangle className="h-5 w-5 text-red-500" />
                )}
                <div>
                  <p className="font-medium">Connection Status</p>
                  <p className="text-sm text-muted-foreground">
                    {mockDatabaseConfig.host}:{mockDatabaseConfig.port}/{mockDatabaseConfig.database}
                  </p>
                </div>
              </div>
              <Badge variant={mockDatabaseConfig.status === 'connected' ? 'success' : 'destructive'}>
                {mockDatabaseConfig.status}
              </Badge>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Host</Label>
                <Input value={mockDatabaseConfig.host} disabled />
              </div>
              <div className="space-y-2">
                <Label>Port</Label>
                <Input value={mockDatabaseConfig.port} disabled />
              </div>
              <div className="space-y-2">
                <Label>Database</Label>
                <Input value={mockDatabaseConfig.database} disabled />
              </div>
              <div className="space-y-2">
                <Label>Connection Pool Size</Label>
                <Input value={mockDatabaseConfig.connectionPoolSize} disabled />
              </div>
            </div>

            <div className="flex justify-end">
              <Button variant="outline" onClick={handleTestDatabase}>
                <RefreshCw className="h-4 w-4 mr-2" />
                Test Connection
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Email Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Mail className="h-5 w-5" />
              Email Configuration
            </CardTitle>
            <CardDescription>SMTP settings for transactional emails</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="smtp-host">SMTP Host</Label>
                <Input
                  id="smtp-host"
                  value={emailConfig.smtpHost}
                  onChange={(e) =>
                    setEmailConfig({ ...emailConfig, smtpHost: e.target.value })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="smtp-port">SMTP Port</Label>
                <Input
                  id="smtp-port"
                  type="number"
                  value={emailConfig.smtpPort}
                  onChange={(e) =>
                    setEmailConfig({ ...emailConfig, smtpPort: parseInt(e.target.value) })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="smtp-user">SMTP Username</Label>
                <Input
                  id="smtp-user"
                  value={emailConfig.smtpUser}
                  onChange={(e) =>
                    setEmailConfig({ ...emailConfig, smtpUser: e.target.value })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="smtp-pass">SMTP Password</Label>
                <Input id="smtp-pass" type="password" placeholder="••••••••" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="from-name">From Name</Label>
                <Input
                  id="from-name"
                  value={emailConfig.fromName}
                  onChange={(e) =>
                    setEmailConfig({ ...emailConfig, fromName: e.target.value })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="from-email">From Email</Label>
                <Input
                  id="from-email"
                  type="email"
                  value={emailConfig.fromEmail}
                  onChange={(e) =>
                    setEmailConfig({ ...emailConfig, fromEmail: e.target.value })
                  }
                />
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={handleTestEmail}>
                <Mail className="h-4 w-4 mr-2" />
                Send Test Email
              </Button>
              <Button onClick={handleSaveEmail} disabled={isSaving}>
                <Save className="h-4 w-4 mr-2" />
                {isSaving ? 'Saving...' : 'Save Changes'}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Environment Variables */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Key className="h-5 w-5" />
              Environment Variables
            </CardTitle>
            <CardDescription>System environment configuration (read-only)</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 font-mono text-sm">
              <div className="flex items-center justify-between p-2 rounded bg-muted">
                <span className="text-muted-foreground">NODE_ENV</span>
                <span>production</span>
              </div>
              <div className="flex items-center justify-between p-2 rounded bg-muted">
                <span className="text-muted-foreground">API_VERSION</span>
                <span>v1</span>
              </div>
              <div className="flex items-center justify-between p-2 rounded bg-muted">
                <span className="text-muted-foreground">MAX_UPLOAD_SIZE</span>
                <span>50MB</span>
              </div>
              <div className="flex items-center justify-between p-2 rounded bg-muted">
                <span className="text-muted-foreground">RATE_LIMIT_ENABLED</span>
                <span>true</span>
              </div>
              <div className="flex items-center justify-between p-2 rounded bg-muted">
                <span className="text-muted-foreground">LOG_LEVEL</span>
                <span>info</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
