// @ts-nocheck
import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { PaginationControls } from '@/components/ui/pagination-controls';
import { ExternalLink, Loader2 } from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { toast } from 'sonner';
import type { PaginatedResponse } from '@/types';

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
  invoices?: Invoice[];
}

export function InvoicesTable({ invoices: initialInvoices }: InvoicesTableProps) {
  const [invoices, setInvoices] = useState<Invoice[]>(initialInvoices || []);
  const [isLoading, setIsLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [totalItems, setTotalItems] = useState(0);
  const [totalPages, setTotalPages] = useState(0);

  useEffect(() => {
    loadInvoices();
  }, [currentPage, pageSize]);

  const loadInvoices = async () => {
    setIsLoading(true);
    try {
      const response = await apiClient.getInvoices({
        page: currentPage,
        pageSize: pageSize
      });

      const paginatedData = response.data as PaginatedResponse<Invoice>;
      setInvoices(paginatedData.items);
      setTotalItems(paginatedData.total);
      setTotalPages(paginatedData.totalPages);
    } catch (error: any) {
      toast.error('Failed to load invoices');
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

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

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Invoices ({totalItems})</CardTitle>
          <CardDescription>Your billing history</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-64">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Invoices ({totalItems})</CardTitle>
        <CardDescription>Your billing history</CardDescription>
      </CardHeader>
      <CardContent>
        {invoices && invoices.length > 0 ? (
          <>
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

            <PaginationControls
              currentPage={currentPage}
              totalPages={totalPages}
              total={totalItems}
              pageSize={pageSize}
              onPageChange={setCurrentPage}
              onPageSizeChange={(newSize) => {
                setPageSize(newSize);
                setCurrentPage(1);
              }}
              isLoading={isLoading}
              itemLabel="invoices"
            />
          </>
        ) : (
          <div className="text-center py-8 text-muted-foreground">
            No invoices yet
          </div>
        )}
      </CardContent>
    </Card>
  );
}
