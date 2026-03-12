import { useSearchParams } from "react-router-dom";
import { useCallback, useRef } from "react";

/**
 * Syncs a piece of state with a URL search parameter.
 *
 * Supports `string`, `number`, and `string[]` values.
 * - Strings are stored / read as-is.
 * - Numbers are stored as strings and parsed on read.
 * - Arrays are stored as comma-separated values.
 *
 * When the value equals `defaultValue`, the parameter is removed
 * from the URL to keep URLs clean.
 */
export function useUrlState<T extends string | number | string[]>(
  key: string,
  defaultValue: T,
): [T, (value: T) => void] {
  const [searchParams, setSearchParams] = useSearchParams();

  // Keep a stable reference for the default so callers don't need to memo.
  const defaultRef = useRef(defaultValue);
  defaultRef.current = defaultValue;

  const rawValue = searchParams.get(key);

  const value: T = (() => {
    const def = defaultRef.current;

    if (rawValue === null) return def;

    // string[]
    if (Array.isArray(def)) {
      return (rawValue ? rawValue.split(",") : []) as T;
    }

    // number
    if (typeof def === "number") {
      const n = Number(rawValue);
      return (Number.isNaN(n) ? def : n) as T;
    }

    // string
    return rawValue as T;
  })();

  const setValue = useCallback(
    (next: T) => {
      setSearchParams(
        (prev) => {
          const sp = new URLSearchParams(prev);
          const def = defaultRef.current;

          // Determine the serialised string for `next`.
          let serialised: string;
          if (Array.isArray(next)) {
            serialised = next.join(",");
          } else {
            serialised = String(next);
          }

          // Determine the serialised string for `defaultValue`.
          let defaultSerialised: string;
          if (Array.isArray(def)) {
            defaultSerialised = (def as string[]).join(",");
          } else {
            defaultSerialised = String(def);
          }

          if (serialised === defaultSerialised || serialised === "") {
            sp.delete(key);
          } else {
            sp.set(key, serialised);
          }

          return sp;
        },
        { replace: true },
      );
    },
    [key, setSearchParams],
  );

  return [value, setValue];
}
