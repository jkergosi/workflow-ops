import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ArrowRight, Shield, GitBranch, History } from 'lucide-react';

export function DashboardUpsellCard() {
  const navigate = useNavigate();

  return (
    <Card className="border-dashed">
      <CardHeader>
        <CardTitle>Unlock Advanced Controls</CardTitle>
        <CardDescription>
          Upgrade to Pro to access advanced monitoring and management features
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <ul className="space-y-2 text-sm text-muted-foreground">
          <li className="flex items-start gap-2">
            <Shield className="h-4 w-4 mt-0.5 flex-shrink-0" />
            <span>Credential Health monitoring</span>
          </li>
          <li className="flex items-start gap-2">
            <GitBranch className="h-4 w-4 mt-0.5 flex-shrink-0" />
            <span>Environment drift detection</span>
          </li>
          <li className="flex items-start gap-2">
            <History className="h-4 w-4 mt-0.5 flex-shrink-0" />
            <span>Extended execution history</span>
          </li>
        </ul>
        <Button onClick={() => navigate('/admin/providers')} className="w-full gap-2">
          Upgrade to Pro
          <ArrowRight className="h-4 w-4" />
        </Button>
      </CardContent>
    </Card>
  );
}

