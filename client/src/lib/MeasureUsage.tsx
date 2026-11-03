// Runs usage measurement and renders nothing (#1902). Loaded behind import()
// by lib/DeferredMeasureUsage.tsx; lib/useUsageMeasurement.ts is the whole of
// what it does.

import { useEffect } from 'react'

import {
  type UsageMeasurement,
  type UsageMeasurementInput,
  useUsageMeasurement,
} from './useUsageMeasurement'

export interface MeasureUsageProps {
  input: UsageMeasurementInput
  /**
   * Given `planMade` and `planCompleted` once measurement is running, and
   * null when it stops - where App's plan handlers find them.
   */
  onMeasure: (measurement: UsageMeasurement | null) => void
}

export function MeasureUsage({ input, onMeasure }: MeasureUsageProps): null {
  const measurement = useUsageMeasurement(input)
  useEffect(() => {
    onMeasure(measurement)
    return () => onMeasure(null)
  }, [onMeasure, measurement])
  return null
}
