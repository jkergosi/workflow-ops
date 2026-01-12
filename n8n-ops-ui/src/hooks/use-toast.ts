import { toast as sonnerToast } from 'sonner';

/**
 * Toast hook that wraps sonner's toast functionality.
 * Provides a consistent API for displaying toast notifications.
 *
 * @example
 * const { toast } = useToast();
 *
 * // Success toast
 * toast({
 *   title: 'Success',
 *   description: 'Operation completed successfully',
 * });
 *
 * // Error toast
 * toast({
 *   title: 'Error',
 *   description: 'Something went wrong',
 *   variant: 'destructive',
 * });
 */

interface ToastOptions {
  title: string;
  description?: string;
  variant?: 'default' | 'destructive';
}

export function useToast() {
  const toast = ({ title, description, variant = 'default' }: ToastOptions) => {
    // Use sonner's built-in title and description support
    if (variant === 'destructive') {
      sonnerToast.error(title, {
        description: description,
      });
    } else {
      sonnerToast.success(title, {
        description: description,
      });
    }
  };

  return { toast };
}
