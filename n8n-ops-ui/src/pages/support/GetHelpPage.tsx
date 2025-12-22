import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ArrowLeft, HelpCircle, CheckCircle, ExternalLink, Loader2 } from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { v4 as uuidv4 } from 'uuid';

interface HelpFormData {
  title: string;
  details: string;
  includeDiagnostics: boolean;
}

export function GetHelpPage() {
  useEffect(() => {
    document.title = 'Get Help - n8n Ops';
    return () => {
      document.title = 'n8n Ops';
    };
  }, []);

  const navigate = useNavigate();

  const [formData, setFormData] = useState<HelpFormData>({
    title: '',
    details: '',
    includeDiagnostics: true,
  });

  const [showSuccess, setShowSuccess] = useState(false);
  const [jsmKey, setJsmKey] = useState('');

  // Fetch config for portal URL
  const { data: configData } = useQuery({
    queryKey: ['support-config'],
    queryFn: () => apiClient.getSupportConfig(),
  });

  const jsmPortalUrl = configData?.data?.jsm_portal_url;

  const mutation = useMutation({
    mutationFn: async (data: HelpFormData) => {
      // Collect diagnostics if enabled
      const diagnostics = data.includeDiagnostics
        ? {
            app_id: 'workflow-ops',
            app_env: import.meta.env.MODE || 'development',
            app_version: import.meta.env.VITE_APP_VERSION || 'unknown',
            git_sha: import.meta.env.VITE_GIT_SHA || 'unknown',
            route: window.location.pathname,
            correlation_id: uuidv4(),
          }
        : undefined;

      return apiClient.createSupportRequest({
        intent_kind: 'task',
        help_request: {
          title: data.title,
          details: data.details,
          include_diagnostics: data.includeDiagnostics,
        },
        diagnostics,
      });
    },
    onSuccess: (response) => {
      setJsmKey(response.data.jsm_request_key);
      setShowSuccess(true);
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to submit help request';
      toast.error(message);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    // Validate required fields
    if (!formData.title.trim()) {
      toast.error('Title is required');
      return;
    }
    if (!formData.details.trim()) {
      toast.error('Please describe what you need help with');
      return;
    }

    mutation.mutate(formData);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate('/support')}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <HelpCircle className="h-8 w-8 text-blue-600" />
            Get Help
          </h1>
          <p className="text-muted-foreground">
            Ask questions or get assistance
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <Card>
          <CardHeader>
            <CardTitle>How can we help?</CardTitle>
            <CardDescription>
              Describe your question or what you need assistance with
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Title */}
            <div className="space-y-2">
              <Label htmlFor="title">
                Title <span className="text-red-500">*</span>
              </Label>
              <Input
                id="title"
                placeholder="Brief summary of your question"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                maxLength={255}
              />
            </div>

            {/* Details */}
            <div className="space-y-2">
              <Label htmlFor="details">
                Question / Details <span className="text-red-500">*</span>
              </Label>
              <Textarea
                id="details"
                placeholder="Provide as much context as possible about your question or what you need help with..."
                value={formData.details}
                onChange={(e) => setFormData({ ...formData, details: e.target.value })}
                rows={6}
              />
            </div>

            {/* Include diagnostics */}
            <div className="flex items-center justify-between rounded-lg border p-4">
              <div className="space-y-0.5">
                <Label htmlFor="diagnostics" className="text-base">
                  Include diagnostics
                </Label>
                <p className="text-sm text-muted-foreground">
                  Automatically include app version, environment, and current page info
                </p>
              </div>
              <Switch
                id="diagnostics"
                checked={formData.includeDiagnostics}
                onCheckedChange={(checked) =>
                  setFormData({ ...formData, includeDiagnostics: checked })
                }
              />
            </div>

            {/* Submit button */}
            <div className="flex justify-end gap-4">
              <Button type="button" variant="outline" onClick={() => navigate('/support')}>
                Cancel
              </Button>
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Submit Request
              </Button>
            </div>
          </CardContent>
        </Card>
      </form>

      {/* Success Dialog */}
      <Dialog open={showSuccess} onOpenChange={setShowSuccess}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-green-600" />
              Help Request Submitted
            </DialogTitle>
            <DialogDescription>
              Your help request has been submitted successfully.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <p className="text-sm text-muted-foreground mb-2">Request ID:</p>
            <p className="text-2xl font-mono font-bold">{jsmKey}</p>
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => navigate('/support')}>
              Back to Support
            </Button>
            {jsmPortalUrl && (
              <Button
                onClick={() => window.open(`${jsmPortalUrl}/requests/${jsmKey}`, '_blank')}
                className="gap-2"
              >
                <ExternalLink className="h-4 w-4" />
                Open in Portal
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
