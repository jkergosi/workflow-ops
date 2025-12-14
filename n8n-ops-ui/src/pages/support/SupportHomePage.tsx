import { Link } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Bug, Lightbulb, HelpCircle, ExternalLink } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';

export function SupportHomePage() {
  // Fetch config to get JSM portal URL
  const { data: configData } = useQuery({
    queryKey: ['support-config'],
    queryFn: () => apiClient.getSupportConfig(),
  });

  const jsmPortalUrl = configData?.data?.jsm_portal_url;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Support</h1>
        <p className="text-muted-foreground">
          Get help, report issues, or request new features
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <Link to="/support/bug/new" className="block">
          <Card className="h-full hover:border-primary transition-colors cursor-pointer">
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-red-100 dark:bg-red-900">
                  <Bug className="h-6 w-6 text-red-600 dark:text-red-400" />
                </div>
                <div>
                  <CardTitle className="text-lg">Report a Bug</CardTitle>
                  <CardDescription>
                    Something not working as expected?
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Report issues, errors, or unexpected behavior. Include details
                about what happened and what you expected.
              </p>
            </CardContent>
          </Card>
        </Link>

        <Link to="/support/feature/new" className="block">
          <Card className="h-full hover:border-primary transition-colors cursor-pointer">
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-amber-100 dark:bg-amber-900">
                  <Lightbulb className="h-6 w-6 text-amber-600 dark:text-amber-400" />
                </div>
                <div>
                  <CardTitle className="text-lg">Request a Feature</CardTitle>
                  <CardDescription>
                    Have an idea for improvement?
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Share your ideas for new features or enhancements. Tell us what
                problem you're trying to solve.
              </p>
            </CardContent>
          </Card>
        </Link>

        <Link to="/support/help/new" className="block">
          <Card className="h-full hover:border-primary transition-colors cursor-pointer">
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-blue-100 dark:bg-blue-900">
                  <HelpCircle className="h-6 w-6 text-blue-600 dark:text-blue-400" />
                </div>
                <div>
                  <CardTitle className="text-lg">Get Help</CardTitle>
                  <CardDescription>
                    Need assistance or guidance?
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Ask questions, get troubleshooting help, or request guidance on
                using the platform.
              </p>
            </CardContent>
          </Card>
        </Link>
      </div>

      <hr className="my-6" />

      <div>
        <Button
          variant="outline"
          className="gap-2"
          onClick={() => {
            if (jsmPortalUrl) {
              window.open(jsmPortalUrl, '_blank');
            } else {
              window.open('https://support.example.com', '_blank');
            }
          }}
        >
          <ExternalLink className="h-4 w-4" />
          View my support requests
        </Button>
        <p className="text-sm text-muted-foreground mt-2">
          Opens the support portal in a new tab to view all your requests, updates, and history.
        </p>
      </div>
    </div>
  );
}
