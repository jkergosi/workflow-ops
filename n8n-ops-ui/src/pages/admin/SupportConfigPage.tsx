import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Loader2, Save, TestTube, CheckCircle, XCircle, Webhook, Settings2, FileText } from 'lucide-react';
import { apiClient } from '@/lib/api-client';

interface SupportConfigFormData {
  n8n_webhook_url: string;
  n8n_api_key: string;
  jsm_portal_url: string;
  jsm_cloud_instance: string;
  jsm_api_token: string;
  jsm_project_key: string;
  jsm_bug_request_type_id: string;
  jsm_feature_request_type_id: string;
  jsm_help_request_type_id: string;
  jsm_widget_embed_code: string;
}

export function SupportConfigPage() {
  const queryClient = useQueryClient();

  const [formData, setFormData] = useState<SupportConfigFormData>({
    n8n_webhook_url: '',
    n8n_api_key: '',
    jsm_portal_url: '',
    jsm_cloud_instance: '',
    jsm_api_token: '',
    jsm_project_key: '',
    jsm_bug_request_type_id: '',
    jsm_feature_request_type_id: '',
    jsm_help_request_type_id: '',
    jsm_widget_embed_code: '',
  });

  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  const { data: configData, isLoading } = useQuery({
    queryKey: ['support-config'],
    queryFn: () => apiClient.getSupportConfig(),
  });

  useEffect(() => {
    if (configData?.data) {
      setFormData({
        n8n_webhook_url: configData.data.n8n_webhook_url || '',
        n8n_api_key: configData.data.n8n_api_key || '',
        jsm_portal_url: configData.data.jsm_portal_url || '',
        jsm_cloud_instance: configData.data.jsm_cloud_instance || '',
        jsm_api_token: configData.data.jsm_api_token || '',
        jsm_project_key: configData.data.jsm_project_key || '',
        jsm_bug_request_type_id: configData.data.jsm_bug_request_type_id || '',
        jsm_feature_request_type_id: configData.data.jsm_feature_request_type_id || '',
        jsm_help_request_type_id: configData.data.jsm_help_request_type_id || '',
        jsm_widget_embed_code: configData.data.jsm_widget_embed_code || '',
      });
    }
  }, [configData]);

  const updateMutation = useMutation({
    mutationFn: (data: Partial<SupportConfigFormData>) => apiClient.updateSupportConfig(data),
    onSuccess: () => {
      toast.success('Configuration saved successfully');
      queryClient.invalidateQueries({ queryKey: ['support-config'] });
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to save configuration';
      toast.error(message);
    },
  });

  const testMutation = useMutation({
    mutationFn: () => apiClient.testN8nConnection(),
    onSuccess: (response) => {
      setTestResult(response.data);
      if (response.data.success) {
        toast.success('Connection successful');
      } else {
        toast.error(response.data.message);
      }
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Connection test failed';
      setTestResult({ success: false, message });
      toast.error(message);
    },
  });

  const handleSave = () => {
    // Only send non-empty fields
    const dataToSave: Partial<SupportConfigFormData> = {};
    Object.entries(formData).forEach(([key, value]) => {
      if (value) {
        dataToSave[key as keyof SupportConfigFormData] = value;
      }
    });
    updateMutation.mutate(dataToSave);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Support Configuration</h1>
        <p className="text-muted-foreground">
          Configure n8n integration and Jira Service Management settings
        </p>
      </div>

      <Tabs defaultValue="n8n" className="space-y-4">
        <TabsList>
          <TabsTrigger value="n8n" className="gap-2">
            <Webhook className="h-4 w-4" />
            n8n Integration
          </TabsTrigger>
          <TabsTrigger value="jsm" className="gap-2">
            <Settings2 className="h-4 w-4" />
            JSM Settings
          </TabsTrigger>
          <TabsTrigger value="request-types" className="gap-2">
            <FileText className="h-4 w-4" />
            Request Types
          </TabsTrigger>
        </TabsList>

        <TabsContent value="n8n" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>n8n Webhook Configuration</CardTitle>
              <CardDescription>
                Configure the n8n webhook endpoint that receives support requests
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="n8n_webhook_url">Webhook URL</Label>
                <Input
                  id="n8n_webhook_url"
                  type="url"
                  placeholder="https://your-n8n.com/webhook/support"
                  value={formData.n8n_webhook_url}
                  onChange={(e) => setFormData({ ...formData, n8n_webhook_url: e.target.value })}
                />
                <p className="text-sm text-muted-foreground">
                  The n8n webhook URL that will receive support request payloads
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="n8n_api_key">API Key (optional)</Label>
                <Input
                  id="n8n_api_key"
                  type="password"
                  placeholder="Enter API key for authentication"
                  value={formData.n8n_api_key}
                  onChange={(e) => setFormData({ ...formData, n8n_api_key: e.target.value })}
                />
                <p className="text-sm text-muted-foreground">
                  Optional API key for authenticating with the n8n webhook
                </p>
              </div>

              <div className="flex items-center gap-4 pt-4">
                <Button
                  variant="outline"
                  onClick={() => testMutation.mutate()}
                  disabled={!formData.n8n_webhook_url || testMutation.isPending}
                >
                  {testMutation.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <TestTube className="mr-2 h-4 w-4" />
                  )}
                  Test Connection
                </Button>
                {testResult && (
                  <Badge variant={testResult.success ? 'default' : 'destructive'} className="gap-1">
                    {testResult.success ? (
                      <CheckCircle className="h-3 w-3" />
                    ) : (
                      <XCircle className="h-3 w-3" />
                    )}
                    {testResult.message}
                  </Badge>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="jsm" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Jira Service Management Settings</CardTitle>
              <CardDescription>
                Configure your JSM portal and API connection
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="jsm_cloud_instance">Cloud Instance URL</Label>
                  <Input
                    id="jsm_cloud_instance"
                    type="url"
                    placeholder="https://yourcompany.atlassian.net"
                    value={formData.jsm_cloud_instance}
                    onChange={(e) => setFormData({ ...formData, jsm_cloud_instance: e.target.value })}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="jsm_project_key">Project Key</Label>
                  <Input
                    id="jsm_project_key"
                    placeholder="SUP"
                    value={formData.jsm_project_key}
                    onChange={(e) => setFormData({ ...formData, jsm_project_key: e.target.value })}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="jsm_portal_url">Customer Portal URL</Label>
                <Input
                  id="jsm_portal_url"
                  type="url"
                  placeholder="https://yourcompany.atlassian.net/servicedesk/customer/portal/1"
                  value={formData.jsm_portal_url}
                  onChange={(e) => setFormData({ ...formData, jsm_portal_url: e.target.value })}
                />
                <p className="text-sm text-muted-foreground">
                  Used for "View in portal" links shown to users after submitting requests
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="jsm_api_token">API Token (optional)</Label>
                <Input
                  id="jsm_api_token"
                  type="password"
                  placeholder="Enter Atlassian API token"
                  value={formData.jsm_api_token}
                  onChange={(e) => setFormData({ ...formData, jsm_api_token: e.target.value })}
                />
                <p className="text-sm text-muted-foreground">
                  Optional token for fetching live request status from JSM
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="jsm_widget_embed_code">Widget Embed Code (optional)</Label>
                <Textarea
                  id="jsm_widget_embed_code"
                  placeholder="<script>...</script>"
                  value={formData.jsm_widget_embed_code}
                  onChange={(e) => setFormData({ ...formData, jsm_widget_embed_code: e.target.value })}
                  rows={4}
                />
                <p className="text-sm text-muted-foreground">
                  JavaScript embed code for the JSM help widget
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="request-types" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>JSM Request Type Mapping</CardTitle>
              <CardDescription>
                Map support request types to their corresponding JSM request type IDs
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="jsm_bug_request_type_id">Bug Report Request Type ID</Label>
                <Input
                  id="jsm_bug_request_type_id"
                  placeholder="e.g., 10001"
                  value={formData.jsm_bug_request_type_id}
                  onChange={(e) => setFormData({ ...formData, jsm_bug_request_type_id: e.target.value })}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="jsm_feature_request_type_id">Feature Request Type ID</Label>
                <Input
                  id="jsm_feature_request_type_id"
                  placeholder="e.g., 10002"
                  value={formData.jsm_feature_request_type_id}
                  onChange={(e) => setFormData({ ...formData, jsm_feature_request_type_id: e.target.value })}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="jsm_help_request_type_id">Help / Question Request Type ID</Label>
                <Input
                  id="jsm_help_request_type_id"
                  placeholder="e.g., 10003"
                  value={formData.jsm_help_request_type_id}
                  onChange={(e) => setFormData({ ...formData, jsm_help_request_type_id: e.target.value })}
                />
              </div>

              <p className="text-sm text-muted-foreground pt-2">
                You can find request type IDs in your JSM project settings under Request Types.
              </p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={updateMutation.isPending}>
          {updateMutation.isPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Save className="mr-2 h-4 w-4" />
          )}
          Save Configuration
        </Button>
      </div>
    </div>
  );
}
