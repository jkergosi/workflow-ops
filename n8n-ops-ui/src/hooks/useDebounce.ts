import { useEffect, useState } from 'react';

/**
 * Debounce a value by a specified delay.
 * 
 * Useful for search inputs to prevent excessive API calls while typing.
 * 
 * @param value - The value to debounce
 * @param delay - Delay in milliseconds (default 300ms)
 * @returns The debounced value
 * 
 * @example
 * const [searchInput, setSearchInput] = useState('');
 * const debouncedSearch = useDebounce(searchInput, 300);
 * 
 * // Use debouncedSearch in your query
 * useQuery({
 *   queryKey: ['items', debouncedSearch],
 *   queryFn: () => api.search(debouncedSearch),
 * });
 */
export function useDebounce<T>(value: T, delay: number = 300): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}

