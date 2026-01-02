/**
 * Billing utility functions for formatting limits, usage, and checking near-limit states
 */

export type LimitValue = string | number | null | undefined;

/**
 * Format a limit value for display
 * @param value - The limit value (number, "Unlimited", "Custom", null, undefined)
 * @returns Formatted string: "Unlimited" | "Custom" | "—" | <number>
 */
export function formatLimit(value: LimitValue): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'string') {
    const lower = value.toLowerCase();
    if (lower === 'unlimited' || lower === 'inf' || lower === '-1') return 'Unlimited';
    if (lower === 'custom') return 'Custom';
    // Try to parse as number
    const num = parseFloat(value);
    if (!isNaN(num)) {
      if (num === -1 || num >= 9999) return 'Unlimited';
      return String(Math.floor(num));
    }
    return value;
  }
  if (typeof value === 'number') {
    if (value === -1 || value >= 9999) return 'Unlimited';
    return String(Math.floor(value));
  }
  return '—';
}

/**
 * Format usage display: "used / limit"
 * @param used - Current usage count
 * @param limit - Limit value (formatted by formatLimit)
 * @returns Formatted string like "5 / 10" or "5 / Unlimited"
 */
export function formatUsage(used: number, limit: LimitValue): string {
  const formattedLimit = formatLimit(limit);
  return `${used} / ${formattedLimit}`;
}

/**
 * Check if usage is near the limit (>= 80%)
 * @param used - Current usage count
 * @param limit - Limit value
 * @returns true if usage is >= 80% of limit
 */
export function isNearLimit(used: number, limit: LimitValue): boolean {
  if (!limit || limit === 'Unlimited' || limit === 'Custom' || limit === '—') return false;
  
  const limitNum = typeof limit === 'string' ? parseFloat(limit) : limit;
  if (isNaN(limitNum) || limitNum <= 0) return false;
  
  const percentage = (used / limitNum) * 100;
  return percentage >= 80;
}

/**
 * Calculate usage percentage
 * @param used - Current usage count
 * @param limit - Limit value
 * @returns Percentage (0-100) or 0 if unlimited/invalid
 */
export function getUsagePercentage(used: number, limit: LimitValue): number {
  if (!limit || limit === 'Unlimited' || limit === 'Custom' || limit === '—') return 0;
  
  const limitNum = typeof limit === 'string' ? parseFloat(limit) : limit;
  if (isNaN(limitNum) || limitNum <= 0) return 0;
  
  return Math.min((used / limitNum) * 100, 100);
}

