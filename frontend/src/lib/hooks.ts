import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from './api'
import type { Meta } from './types'

export interface Loaded<T> { data: T | null; meta: Meta; loading: boolean; error: string | null; reload: () => void }

/** Runs `fn` whenever `key` changes; ignores out-of-date responses. */
export function useLoad<T>(fn: () => Promise<{ data: T; meta?: Meta }>, key: string): Loaded<T> {
  const [state, setState] = useState<{ data: T | null; meta: Meta; loading: boolean; error: string | null }>({ data: null, meta: {}, loading: true, error: null })
  const [tick, setTick] = useState(0)
  const fnRef = useRef(fn)
  fnRef.current = fn
  useEffect(() => {
    let live = true
    setState(s => ({ ...s, loading: true, error: null }))
    fnRef.current().then(
      r => { if (live) setState({ data: r.data, meta: r.meta ?? {}, loading: false, error: null }) },
      (e: unknown) => { if (live) setState(s => ({ ...s, loading: false, error: e instanceof ApiError || e instanceof Error ? e.message : 'Something went wrong.' })) },
    )
    return () => { live = false }
  }, [key, tick])
  const reload = useCallback(() => setTick(t => t + 1), [])
  return { ...state, reload }
}

export function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value)
  useEffect(() => { const t = setTimeout(() => setV(value), ms); return () => clearTimeout(t) }, [value, ms])
  return v
}

export const errorMessage = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong.')

import { get } from './api'
import type { Metadata } from './types'
export const useMetadata = () => useLoad<Metadata>(() => get<Metadata>('/api/metadata'), 'metadata')
