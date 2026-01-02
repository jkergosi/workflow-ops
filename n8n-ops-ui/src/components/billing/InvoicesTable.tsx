// @ts-nocheck
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ExternalLink } from 'lucide-react';

interface Invoice {
  id: string;
  number?: string;
  amount_paid: number;
  amount_paid_cents?: number;
  currency: string;
  status: string;
  created: number;
  invoice_pdf?: string;
  hosted_invoice_url?: string;
}

interface InvoicesTableProps {
  invoices: Invoice[];
}

export function InvoicesTable({ invoices }: InvoicesTableProps) {
  const formatCurrency = (cents: number | null | undefined, currency: string = 'USD') => {
    if (cents === null || cents === undefined) return '—';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency,
    }).format(cents / 100);
  };

  const formatInvoiceDate = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const getStatusBadgeVariant = (status: string) => {
    switch (status.toLowerCase()) {
      case 'paid':
        return 'default';
      case 'open':
        return 'secondary';
      case 'uncollectible':
      case 'void':
        return 'destructive';
      default:
        return 'outline';
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Invoices</CardTitle>
        <CardDescription>Your billing history</CardDescription>
      </CardHeader>
      <CardContent>
        {invoices && invoices.length > 0 ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Invoice #</TableHead>
                <TableHead>Amount</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Download</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {invoices.map((invoice) => (
                <TableRow key={invoice.id}>
                  <TableCell>{formatInvoiceDate(invoice.created)}</TableCell>
                  <TableCell className="font-mono text-sm">
                    {invoice.number || invoice.id}
                  </TableCell>
                  <TableCell>
                    {formatCurrency(
                      invoice.amount_paid_cents || invoice.amount_paid * 100,
                      invoice.currency
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant={getStatusBadgeVariant(invoice.status)}>
                      {invoice.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    {invoice.invoice_pdf && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => window.open(invoice.invoice_pdf, '_blank')}
                      >
                        <ExternalLink className="h-4 w-4 mr-1" />
                        PDF
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <div className="text-center py-8 text-muted-foreground">
            No invoices yet
          </div>
        )}
      </CardContent>
    </Card>
  );
}

