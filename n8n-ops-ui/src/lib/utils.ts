import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Extracts error message from API error responses.
 * Handles both string error messages and entitlement error objects.
 *
 * @param error - Axios error object
 * @param fallback - Fallback message if extraction fails
 * @returns Error message string safe for display in toast/UI
 */
export function getErrorMessage(error: any, fallback: string = 'An error occurred'): string {
  const detail = error?.response?.data?.detail;

  // Handle entitlement error objects with message property
  if (typeof detail === 'object' && detail?.message) {
    return detail.message;
  }

  // Handle string error messages
  if (typeof detail === 'string') {
    return detail;
  }

  // Fallback
  return fallback;
}
