import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ArrowLeft, Bug, CheckCircle, ExternalLink, Loader2 } from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { v4 as uuidv4 } from 'uuid';

interface BugFormData {
  title: string;
  whatHappened: string;
  expectedBehavior: string;
  stepsToReproduce: string;
  severity: string;
  frequency: string;
  includeDiagnostics: boolean;
}

export function ReportBugPage() {
  const navigate = useNavigate();

  const [formData, setFormData] = useState<BugFormData>({
    title: '',
    whatHappened: '',
    expectedBehavior: '',
    stepsToReproduce: '',
    severity: '',
    frequency: '',
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
    mutationFn: async (data: BugFormData) => {
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
        intent_kind: 'bug',
        bug_report: {
          title: data.title,
          what_happened: data.whatHappened,
          expected_behavior: data.expectedBehavior,
          steps_to_reproduce: data.stepsToReproduce || undefined,
          severity: data.severity || undefined,
          frequency: data.frequency || undefined,
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
      const message = error.response?.data?.detail || 'Failed to submit bug report';
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
    if (!formData.whatHappened.trim()) {
      toast.error('Please describe what happened');
      return;
    }
    if (!formData.expectedBehavior.trim()) {
      toast.error('Please describe what you expected');
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
            <Bug className="h-8 w-8 text-red-600" />
            Report a Bug
          </h1>
          <p className="text-muted-foreground">
            Tell us about the issue you're experiencing
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <Card>
          <CardHeader>
            <CardTitle>Bug Details</CardTitle>
            <CardDescription>
              Provide as much detail as possible to help us understand and fix the issue
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
                placeholder="Brief description of the issue"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                maxLength={255}
              />
            </div>

            {/* What happened */}
            <div className="space-y-2">
              <Label htmlFor="whatHappened">
                What happened? <span className="text-red-500">*</span>
              </Label>
              <Textarea
                id="whatHappened"
                placeholder="Describe the issue in detail. What were you trying to do? What error messages did you see?"
                value={formData.whatHappened}
                onChange={(e) => setFormData({ ...formData, whatHappened: e.target.value })}
                rows={4}
              />
            </div>

            {/* Expected behavior */}
            <div className="space-y-2">
              <Label htmlFor="expectedBehavior">
                What did you expect? <span className="text-red-500">*</span>
              </Label>
              <Textarea
                id="expectedBehavior"
                placeholder="Describe what you expected to happen instead"
                value={formData.expectedBehavior}
                onChange={(e) => setFormData({ ...formData, expectedBehavior: e.target.value })}
                rows={3}
              />
            </div>

            {/* Steps to reproduce */}
            <div className="space-y-2">
              <Label htmlFor="stepsToReproduce">Steps to reproduce (optional)</Label>
              <Textarea
                id="stepsToReproduce"
                placeholder="1. Go to...&#10;2. Click on...&#10;3. See error"
                value={formData.stepsToReproduce}
                onChange={(e) => setFormData({ ...formData, stepsToReproduce: e.target.value })}
                rows={4}
              />
            </div>

            <div className="grid gap-6 md:grid-cols-2">
              {/* Severity */}
              <div className="space-y-2">
                <Label htmlFor="severity">Severity (optional)</Label>
                <Select
                  value={formData.severity}
                  onValueChange={(value) => setFormData({ ...formData, severity: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select severity" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="sev1">Critical - System unusable</SelectItem>
                    <SelectItem value="sev2">High - Major feature broken</SelectItem>
                    <SelectItem value="sev3">Medium - Feature impaired</SelectItem>
                    <SelectItem value="sev4">Low - Minor inconvenience</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Frequency */}
              <div className="space-y-2">
                <Label htmlFor="frequency">Frequency (optional)</Label>
                <Select
                  value={formData.frequency}
                  onValueChange={(value) => setFormData({ ...formData, frequency: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="How often does this happen?" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="always">Always</SelectItem>
                    <SelectItem value="intermittent">Sometimes</SelectItem>
                    <SelectItem value="once">Happened once</SelectItem>
                  </SelectContent>
                </Select>
              </div>
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
                Submit Bug Report
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
              Bug Report Submitted
            </DialogTitle>
            <DialogDescription>
              Your bug report has been submitted successfully.
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
