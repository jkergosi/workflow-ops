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
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ArrowLeft, Lightbulb, CheckCircle, ExternalLink, Loader2, Plus, X } from 'lucide-react';
import { apiClient } from '@/lib/api-client';

interface FeatureFormData {
  title: string;
  problemGoal: string;
  desiredOutcome: string;
  priority: string;
  acceptanceCriteria: string[];
  whoIsThisFor: string;
}

export function RequestFeaturePage() {
  const navigate = useNavigate();

  const [formData, setFormData] = useState<FeatureFormData>({
    title: '',
    problemGoal: '',
    desiredOutcome: '',
    priority: '',
    acceptanceCriteria: [],
    whoIsThisFor: '',
  });

  const [newCriterion, setNewCriterion] = useState('');
  const [showSuccess, setShowSuccess] = useState(false);
  const [jsmKey, setJsmKey] = useState('');

  // Fetch config for portal URL
  const { data: configData } = useQuery({
    queryKey: ['support-config'],
    queryFn: () => apiClient.getSupportConfig(),
  });

  const jsmPortalUrl = configData?.data?.jsm_portal_url;

  const mutation = useMutation({
    mutationFn: async (data: FeatureFormData) => {
      return apiClient.createSupportRequest({
        intent_kind: 'feature',
        feature_request: {
          title: data.title,
          problem_goal: data.problemGoal,
          desired_outcome: data.desiredOutcome,
          priority: data.priority || undefined,
          acceptance_criteria: data.acceptanceCriteria.length > 0 ? data.acceptanceCriteria : undefined,
          who_is_this_for: data.whoIsThisFor || undefined,
        },
      });
    },
    onSuccess: (response) => {
      setJsmKey(response.data.jsm_request_key);
      setShowSuccess(true);
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to submit feature request';
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
    if (!formData.problemGoal.trim()) {
      toast.error('Please describe the problem or goal');
      return;
    }
    if (!formData.desiredOutcome.trim()) {
      toast.error('Please describe the desired outcome');
      return;
    }

    mutation.mutate(formData);
  };

  const addCriterion = () => {
    if (newCriterion.trim()) {
      setFormData({
        ...formData,
        acceptanceCriteria: [...formData.acceptanceCriteria, newCriterion.trim()],
      });
      setNewCriterion('');
    }
  };

  const removeCriterion = (index: number) => {
    setFormData({
      ...formData,
      acceptanceCriteria: formData.acceptanceCriteria.filter((_, i) => i !== index),
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate('/support')}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <Lightbulb className="h-8 w-8 text-amber-600" />
            Request a Feature
          </h1>
          <p className="text-muted-foreground">
            Share your ideas for new features or improvements
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <Card>
          <CardHeader>
            <CardTitle>Feature Details</CardTitle>
            <CardDescription>
              Help us understand what you need and why
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
                placeholder="Brief description of the feature"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                maxLength={255}
              />
            </div>

            {/* Problem / Goal */}
            <div className="space-y-2">
              <Label htmlFor="problemGoal">
                Problem / Goal <span className="text-red-500">*</span>
              </Label>
              <Textarea
                id="problemGoal"
                placeholder="What problem are you trying to solve? What goal are you trying to achieve?"
                value={formData.problemGoal}
                onChange={(e) => setFormData({ ...formData, problemGoal: e.target.value })}
                rows={4}
              />
            </div>

            {/* Desired Outcome */}
            <div className="space-y-2">
              <Label htmlFor="desiredOutcome">
                Desired Outcome <span className="text-red-500">*</span>
              </Label>
              <Textarea
                id="desiredOutcome"
                placeholder="What would success look like? How would this feature work?"
                value={formData.desiredOutcome}
                onChange={(e) => setFormData({ ...formData, desiredOutcome: e.target.value })}
                rows={4}
              />
            </div>

            {/* Priority */}
            <div className="space-y-2">
              <Label htmlFor="priority">Priority (optional)</Label>
              <Select
                value={formData.priority}
                onValueChange={(value) => setFormData({ ...formData, priority: value })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="How important is this to you?" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="high">High - Critical to my workflow</SelectItem>
                  <SelectItem value="medium">Medium - Would improve my work</SelectItem>
                  <SelectItem value="low">Low - Nice to have</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Acceptance Criteria */}
            <div className="space-y-2">
              <Label>Acceptance Criteria (optional)</Label>
              <p className="text-sm text-muted-foreground">
                Define what "done" looks like for this feature
              </p>
              <div className="flex gap-2">
                <Input
                  placeholder="Add a criterion..."
                  value={newCriterion}
                  onChange={(e) => setNewCriterion(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      addCriterion();
                    }
                  }}
                />
                <Button type="button" variant="outline" onClick={addCriterion}>
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              {formData.acceptanceCriteria.length > 0 && (
                <ul className="space-y-2 mt-2">
                  {formData.acceptanceCriteria.map((criterion, index) => (
                    <li
                      key={index}
                      className="flex items-center gap-2 p-2 rounded-md bg-muted"
                    >
                      <span className="flex-1 text-sm">{criterion}</span>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => removeCriterion(index)}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Who is this for */}
            <div className="space-y-2">
              <Label htmlFor="whoIsThisFor">Who is this for? (optional)</Label>
              <Input
                id="whoIsThisFor"
                placeholder="e.g., Developers, Administrators, All users"
                value={formData.whoIsThisFor}
                onChange={(e) => setFormData({ ...formData, whoIsThisFor: e.target.value })}
              />
            </div>

            {/* Submit button */}
            <div className="flex justify-end gap-4">
              <Button type="button" variant="outline" onClick={() => navigate('/support')}>
                Cancel
              </Button>
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Submit Feature Request
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
              Feature Request Submitted
            </DialogTitle>
            <DialogDescription>
              Your feature request has been submitted successfully.
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
