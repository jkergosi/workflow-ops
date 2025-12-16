import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Switch } from '@/components/ui/switch';
import {
  Settings,
  Database,
  Mail,
  Key,
  Save,
  RefreshCw,
  CheckCircle,
  AlertTriangle,
  ExternalLink,
  Shield,
  CreditCard,
  Eye,
  EyeOff,
  Copy,
  Webhook,
  TestTube,
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
  provider: 'smtp' | 'sendgrid' | 'aws_ses';
  smtpHost: string;
  smtpPort: number;
  smtpUser: string;
  fromName: string;
  fromEmail: string;
}

interface Auth0Config {
  domain: string;
  clientId: string;
  clientSecret: string;
  audience: string;
  connectionStatus: 'connected' | 'disconnected' | 'error';
  lastSynced?: string;
}

interface StripeConfig {
  mode: 'test' | 'live';
  publishableKey: string;
  secretKey: string;
  webhookSecret: string;
  webhookEndpoint: string;
  webhookStatus: 'active' | 'inactive' | 'error';
  lastWebhookReceived?: string;
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
  provider: 'sendgrid',
  smtpHost: 'smtp.sendgrid.net',
  smtpPort: 587,
  smtpUser: 'apikey',
  fromName: 'N8N Ops',
  fromEmail: 'noreply@n8nops.com',
};

const mockAuth0Config: Auth0Config = {
  domain: 'n8nops.us.auth0.com',
  clientId: 'abc123...xyz789',
  clientSecret: '•••••••••••••••••••••••••',
  audience: 'https://api.n8nops.com',
  connectionStatus: 'connected',
  lastSynced: new Date().toISOString(),
};

const mockStripeConfig: StripeConfig = {
  mode: 'test',
  publishableKey: 'pk_test_...abc123',
  secretKey: 'sk_test_•••••••••••••••',
  webhookSecret: 'whsec_•••••••••••••••',
  webhookEndpoint: 'https://api.n8nops.com/webhooks/stripe',
  webhookStatus: 'active',
  lastWebhookReceived: new Date(Date.now() - 3600000).toISOString(),
};

export function SettingsPage() {
  const [systemConfig, setSystemConfig] = useState(mockSystemConfig);
  const [emailConfig, setEmailConfig] = useState(mockEmailConfig);
  const [isSaving, setIsSaving] = useState(false);
  const [showAuth0Secret, setShowAuth0Secret] = useState(false);
  const [showStripeSecret, setShowStripeSecret] = useState(false);
  const [showWebhookSecret, setShowWebhookSecret] = useState(false);

  const handleSaveSystem = async () => {
    setIsSaving(true);
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

  const handleTestAuth0 = async () => {
    toast.info('Testing Auth0 connection...');
    await new Promise((resolve) => setTimeout(resolve, 1500));
    toast.success('Auth0 connection successful');
  };

  const handleTestStripeWebhook = async () => {
    toast.info('Sending test webhook...');
    await new Promise((resolve) => setTimeout(resolve, 2000));
    toast.success('Webhook test successful');
  };

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    toast.success(`${label} copied to clipboard`);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="text-muted-foreground">Configure system-wide settings and integrations</p>
      </div>

      <Tabs defaultValue="general" className="space-y-6">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="general">General</TabsTrigger>
          <TabsTrigger value="database">Database</TabsTrigger>
          <TabsTrigger value="auth">Auth0</TabsTrigger>
          <TabsTrigger value="payments">Payments</TabsTrigger>
          <TabsTrigger value="email">Email</TabsTrigger>
        </TabsList>

        {/* General Tab */}
        <TabsContent value="general" className="space-y-6">
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
                    <option value="UTC" className="bg-background text-foreground">UTC</option>
                    <option value="America/New_York" className="bg-background text-foreground">Eastern Time</option>
                    <option value="America/Chicago" className="bg-background text-foreground">Central Time</option>
                    <option value="America/Denver" className="bg-background text-foreground">Mountain Time</option>
                    <option value="America/Los_Angeles" className="bg-background text-foreground">Pacific Time</option>
                    <option value="Europe/London" className="bg-background text-foreground">London</option>
                    <option value="Europe/Paris" className="bg-background text-foreground">Paris</option>
                    <option value="Asia/Tokyo" className="bg-background text-foreground">Tokyo</option>
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
                <Switch
                  checked={systemConfig.maintenanceMode}
                  onCheckedChange={(checked) =>
                    setSystemConfig({ ...systemConfig, maintenanceMode: checked })
                  }
                />
              </div>

              <div className="flex justify-end">
                <Button onClick={handleSaveSystem} disabled={isSaving}>
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
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Database Tab */}
        <TabsContent value="database">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Database className="h-5 w-5" />
                Database Connection
              </CardTitle>
              <CardDescription>PostgreSQL database configuration (Supabase)</CardDescription>
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
                <Badge variant={mockDatabaseConfig.status === 'connected' ? 'default' : 'destructive'}>
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

              <div className="p-4 bg-muted/50 rounded-lg">
                <p className="text-sm text-muted-foreground">
                  Database connection is managed through environment variables.
                  Contact your system administrator to modify connection settings.
                </p>
              </div>

              <div className="flex justify-end">
                <Button variant="outline" onClick={handleTestDatabase}>
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Test Connection
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Auth0 Tab */}
        <TabsContent value="auth">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Shield className="h-5 w-5" />
                Auth0 Configuration
              </CardTitle>
              <CardDescription>Authentication and authorization settings</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between p-4 rounded-lg bg-muted/50">
                <div className="flex items-center gap-3">
                  {mockAuth0Config.connectionStatus === 'connected' ? (
                    <CheckCircle className="h-5 w-5 text-green-500" />
                  ) : (
                    <AlertTriangle className="h-5 w-5 text-red-500" />
                  )}
                  <div>
                    <p className="font-medium">Connection Status</p>
                    <p className="text-sm text-muted-foreground">
                      Last synced: {mockAuth0Config.lastSynced ? new Date(mockAuth0Config.lastSynced).toLocaleString() : 'Never'}
                    </p>
                  </div>
                </div>
                <Badge variant={mockAuth0Config.connectionStatus === 'connected' ? 'default' : 'destructive'}>
                  {mockAuth0Config.connectionStatus}
                </Badge>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Auth0 Domain</Label>
                  <div className="flex gap-2">
                    <Input value={mockAuth0Config.domain} disabled className="font-mono" />
                    <Button variant="outline" size="icon" onClick={() => copyToClipboard(mockAuth0Config.domain, 'Domain')}>
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Client ID</Label>
                  <div className="flex gap-2">
                    <Input value={mockAuth0Config.clientId} disabled className="font-mono" />
                    <Button variant="outline" size="icon" onClick={() => copyToClipboard(mockAuth0Config.clientId, 'Client ID')}>
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Client Secret</Label>
                  <div className="flex gap-2">
                    <Input
                      type={showAuth0Secret ? 'text' : 'password'}
                      value={mockAuth0Config.clientSecret}
                      disabled
                      className="font-mono"
                    />
                    <Button variant="outline" size="icon" onClick={() => setShowAuth0Secret(!showAuth0Secret)}>
                      {showAuth0Secret ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </Button>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>API Audience</Label>
                  <Input value={mockAuth0Config.audience} disabled className="font-mono" />
                </div>
              </div>

              <Card className="bg-muted/30">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Callback URLs</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 font-mono text-sm">
                  <div className="p-2 bg-background rounded">https://app.n8nops.com/callback</div>
                  <div className="p-2 bg-background rounded">https://app.n8nops.com/silent-callback</div>
                </CardContent>
              </Card>

              <div className="p-4 bg-muted/50 rounded-lg">
                <p className="text-sm text-muted-foreground">
                  To modify Auth0 configuration, update the values in your environment variables
                  or visit the Auth0 dashboard directly.
                </p>
              </div>

              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={handleTestAuth0}>
                  <TestTube className="h-4 w-4 mr-2" />
                  Test Connection
                </Button>
                <Button variant="outline" asChild>
                  <a href={`https://manage.auth0.com/dashboard/us/${mockAuth0Config.domain.split('.')[0]}`} target="_blank" rel="noopener noreferrer">
                    <ExternalLink className="h-4 w-4 mr-2" />
                    Open Auth0 Dashboard
                  </a>
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Payments Tab */}
        <TabsContent value="payments">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CreditCard className="h-5 w-5" />
                Stripe Configuration
              </CardTitle>
              <CardDescription>Payment processing settings</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Mode Banner */}
              <div className={`p-4 rounded-lg ${mockStripeConfig.mode === 'test' ? 'bg-amber-50 dark:bg-amber-950/50 border border-amber-200 dark:border-amber-800' : 'bg-green-50 dark:bg-green-950/50 border border-green-200 dark:border-green-800'}`}>
                <div className="flex items-center gap-3">
                  <Badge variant={mockStripeConfig.mode === 'test' ? 'outline' : 'default'} className="text-lg px-4 py-1">
                    {mockStripeConfig.mode === 'test' ? 'TEST MODE' : 'LIVE MODE'}
                  </Badge>
                  <p className={`text-sm ${mockStripeConfig.mode === 'test' ? 'text-amber-700 dark:text-amber-300' : 'text-green-700 dark:text-green-300'}`}>
                    {mockStripeConfig.mode === 'test'
                      ? 'Payments are in test mode. No real charges will be made.'
                      : 'Payments are live. Real charges will be processed.'}
                  </p>
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Publishable Key</Label>
                  <div className="flex gap-2">
                    <Input value={mockStripeConfig.publishableKey} disabled className="font-mono" />
                    <Button variant="outline" size="icon" onClick={() => copyToClipboard(mockStripeConfig.publishableKey, 'Publishable Key')}>
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Secret Key</Label>
                  <div className="flex gap-2">
                    <Input
                      type={showStripeSecret ? 'text' : 'password'}
                      value={mockStripeConfig.secretKey}
                      disabled
                      className="font-mono"
                    />
                    <Button variant="outline" size="icon" onClick={() => setShowStripeSecret(!showStripeSecret)}>
                      {showStripeSecret ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </Button>
                  </div>
                </div>
              </div>

              {/* Webhook Configuration */}
              <Card className="bg-muted/30">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Webhook className="h-4 w-4" />
                    Webhook Configuration
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between p-3 rounded-lg bg-background">
                    <div className="flex items-center gap-3">
                      {mockStripeConfig.webhookStatus === 'active' ? (
                        <CheckCircle className="h-5 w-5 text-green-500" />
                      ) : (
                        <AlertTriangle className="h-5 w-5 text-red-500" />
                      )}
                      <div>
                        <p className="font-medium">Webhook Status</p>
                        <p className="text-sm text-muted-foreground">
                          Last received: {mockStripeConfig.lastWebhookReceived ? new Date(mockStripeConfig.lastWebhookReceived).toLocaleString() : 'Never'}
                        </p>
                      </div>
                    </div>
                    <Badge variant={mockStripeConfig.webhookStatus === 'active' ? 'default' : 'destructive'}>
                      {mockStripeConfig.webhookStatus}
                    </Badge>
                  </div>

                  <div className="space-y-2">
                    <Label>Webhook Endpoint</Label>
                    <div className="flex gap-2">
                      <Input value={mockStripeConfig.webhookEndpoint} disabled className="font-mono" />
                      <Button variant="outline" size="icon" onClick={() => copyToClipboard(mockStripeConfig.webhookEndpoint, 'Webhook URL')}>
                        <Copy className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label>Webhook Signing Secret</Label>
                    <div className="flex gap-2">
                      <Input
                        type={showWebhookSecret ? 'text' : 'password'}
                        value={mockStripeConfig.webhookSecret}
                        disabled
                        className="font-mono"
                      />
                      <Button variant="outline" size="icon" onClick={() => setShowWebhookSecret(!showWebhookSecret)}>
                        {showWebhookSecret ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <div className="p-4 bg-muted/50 rounded-lg">
                <p className="text-sm text-muted-foreground">
                  Stripe keys are stored securely in environment variables.
                  Contact your system administrator to change payment configuration.
                </p>
              </div>

              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={handleTestStripeWebhook}>
                  <TestTube className="h-4 w-4 mr-2" />
                  Test Webhook
                </Button>
                <Button variant="outline" asChild>
                  <a href="https://dashboard.stripe.com" target="_blank" rel="noopener noreferrer">
                    <ExternalLink className="h-4 w-4 mr-2" />
                    Open Stripe Dashboard
                  </a>
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Email Tab */}
        <TabsContent value="email">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Mail className="h-5 w-5" />
                Email Configuration
              </CardTitle>
              <CardDescription>Transactional email settings</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Email Provider</Label>
                <select
                  value={emailConfig.provider}
                  onChange={(e) => setEmailConfig({ ...emailConfig, provider: e.target.value as any })}
                  className="flex h-9 w-full rounded-md border border-input bg-background text-foreground px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                >
                  <option value="smtp" className="bg-background text-foreground">SMTP</option>
                  <option value="sendgrid" className="bg-background text-foreground">SendGrid</option>
                  <option value="aws_ses" className="bg-background text-foreground">AWS SES</option>
                </select>
              </div>

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
                  <Label htmlFor="smtp-user">SMTP Username / API Key</Label>
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
        </TabsContent>
      </Tabs>
    </div>
  );
}
