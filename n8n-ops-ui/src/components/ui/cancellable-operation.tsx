/**
 * Cancellable Operation Component
 * For long-running operations that provide cancellation options and background processing
 * with notifications. Reduces user anxiety during long waits.
 */
import * as React from "react"
import { cn } from "@/lib/utils"
import { Progress } from "./progress"
import { Button } from "./button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./card"
import { Alert, AlertDescription } from "./alert"
import {
  Loader2,
  X,
  Clock,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Minimize2,
  Maximize2,
  Bell,
} from "lucide-react"

type OperationStatus = 'idle' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled'

interface CancellableOperationProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Operation title */
  title: string
  /** Operation description */
  description?: string
  /** Current status */
  status: OperationStatus
  /** Progress percentage (0-100) */
  progress?: number
  /** Current step or action being performed */
  currentAction?: string
  /** Estimated time remaining in seconds */
  estimatedTimeRemaining?: number
  /** Whether the operation can be cancelled */
  canCancel?: boolean
  /** Whether the operation can run in background */
  canRunInBackground?: boolean
  /** Callback when cancel is requested */
  onCancel?: () => void
  /** Callback when moving to background */
  onMoveToBackground?: () => void
  /** Callback when bringing back from background */
  onBringToForeground?: () => void
  /** Whether currently running in background */
  isBackground?: boolean
  /** Error message if failed */
  errorMessage?: string
  /** Success message */
  successMessage?: string
  /** Items processed / total (for display) */
  processedCount?: number
  totalCount?: number
  /** Current item being processed */
  currentItem?: string
  /** Start time of operation */
  startTime?: Date
  /** Whether to show as a compact notification-style widget */
  compact?: boolean
}

function formatTime(seconds: number): string {
  if (seconds < 60) {
    return `${Math.round(seconds)}s`
  } else if (seconds < 3600) {
    const mins = Math.floor(seconds / 60)
    const secs = Math.round(seconds % 60)
    return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`
  } else {
    const hours = Math.floor(seconds / 3600)
    const mins = Math.floor((seconds % 3600) / 60)
    return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`
  }
}

const CancellableOperation = React.forwardRef<HTMLDivElement, CancellableOperationProps>(
  ({
    className,
    title,
    description,
    status,
    progress = 0,
    currentAction,
    estimatedTimeRemaining,
    canCancel = true,
    canRunInBackground = true,
    onCancel,
    onMoveToBackground,
    onBringToForeground,
    isBackground = false,
    errorMessage,
    successMessage,
    processedCount,
    totalCount,
    currentItem,
    startTime,
    compact = false,
    ...props
  }, ref) => {
    const [elapsedSeconds, setElapsedSeconds] = React.useState(0)
    const [showCancelConfirm, setShowCancelConfirm] = React.useState(false)

    // Track elapsed time
    React.useEffect(() => {
      if (status !== 'running' || !startTime) return

      const interval = setInterval(() => {
        const elapsed = (Date.now() - startTime.getTime()) / 1000
        setElapsedSeconds(elapsed)
      }, 1000)

      return () => clearInterval(interval)
    }, [status, startTime])

    const getStatusIcon = () => {
      switch (status) {
        case 'running':
          return <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
        case 'paused':
          return <Clock className="h-5 w-5 text-yellow-500" />
        case 'completed':
          return <CheckCircle2 className="h-5 w-5 text-green-500" />
        case 'failed':
          return <XCircle className="h-5 w-5 text-red-500" />
        case 'cancelled':
          return <X className="h-5 w-5 text-muted-foreground" />
        default:
          return null
      }
    }

    const handleCancelClick = () => {
      if (progress > 25) {
        setShowCancelConfirm(true)
      } else {
        onCancel?.()
      }
    }

    // Compact notification-style view
    if (compact && isBackground) {
      return (
        <div
          ref={ref}
          className={cn(
            "fixed bottom-4 right-4 z-50 w-80 bg-background border rounded-lg shadow-lg p-4",
            className
          )}
          {...props}
        >
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2">
              {getStatusIcon()}
              <div className="flex-1 min-w-0">
                <p className="font-medium text-sm truncate">{title}</p>
                <p className="text-xs text-muted-foreground">
                  {status === 'running' && `${Math.round(progress)}% complete`}
                  {status === 'completed' && (successMessage || 'Done')}
                  {status === 'failed' && 'Failed'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              {status === 'running' && (
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-6 w-6"
                  onClick={onBringToForeground}
                >
                  <Maximize2 className="h-3 w-3" />
                </Button>
              )}
              <Button
                size="icon"
                variant="ghost"
                className="h-6 w-6"
                onClick={status === 'running' ? handleCancelClick : undefined}
              >
                <X className="h-3 w-3" />
              </Button>
            </div>
          </div>
          {status === 'running' && (
            <Progress value={progress} className="h-1 mt-2" />
          )}
        </div>
      )
    }

    // Full card view
    return (
      <Card
        ref={ref}
        className={cn(
          "border-2",
          status === 'running' && "border-blue-200 bg-blue-50/30 dark:border-blue-800 dark:bg-blue-950/20",
          status === 'completed' && "border-green-200 bg-green-50/30 dark:border-green-800 dark:bg-green-950/20",
          status === 'failed' && "border-red-200 bg-red-50/30 dark:border-red-800 dark:bg-red-950/20",
          status === 'cancelled' && "border-muted",
          className
        )}
        {...props}
      >
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              {getStatusIcon()}
              <div>
                <CardTitle className="text-base">{title}</CardTitle>
                {description && (
                  <CardDescription className="text-xs mt-0.5">
                    {description}
                  </CardDescription>
                )}
              </div>
            </div>
            <div className="flex items-center gap-1">
              {status === 'running' && canRunInBackground && !isBackground && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={onMoveToBackground}
                  className="h-7 text-xs"
                >
                  <Minimize2 className="h-3 w-3 mr-1" />
                  Background
                </Button>
              )}
              {status === 'running' && canCancel && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={handleCancelClick}
                  className="h-7 text-xs text-muted-foreground hover:text-red-600"
                >
                  <X className="h-3 w-3 mr-1" />
                  Cancel
                </Button>
              )}
            </div>
          </div>
        </CardHeader>

        <CardContent className="space-y-4">
          {/* Progress Section */}
          {status === 'running' && (
            <>
              {/* Current action */}
              {currentAction && (
                <p className="text-sm text-muted-foreground">
                  {currentAction}
                </p>
              )}

              {/* Current item being processed */}
              {currentItem && (
                <p className="text-sm text-muted-foreground truncate">
                  Processing: <span className="font-medium">{currentItem}</span>
                </p>
              )}

              {/* Progress bar */}
              <div className="space-y-2">
                <Progress value={progress} className="h-2" />
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>
                    {processedCount !== undefined && totalCount !== undefined
                      ? `${processedCount} of ${totalCount} (${Math.round(progress)}%)`
                      : `${Math.round(progress)}% complete`
                    }
                  </span>
                  <div className="flex items-center gap-3">
                    {startTime && elapsedSeconds > 0 && (
                      <span>Elapsed: {formatTime(elapsedSeconds)}</span>
                    )}
                    {estimatedTimeRemaining !== undefined && estimatedTimeRemaining > 0 && (
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        ~{formatTime(estimatedTimeRemaining)} left
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Background notification info */}
              {canRunInBackground && !isBackground && (
                <p className="text-xs text-muted-foreground flex items-center gap-1">
                  <Bell className="h-3 w-3" />
                  You'll be notified when complete. Safe to navigate away.
                </p>
              )}
            </>
          )}

          {/* Success state */}
          {status === 'completed' && (
            <Alert className="border-green-200 bg-green-50 dark:bg-green-950/30">
              <CheckCircle2 className="h-4 w-4 text-green-600" />
              <AlertDescription className="text-green-800 dark:text-green-200">
                {successMessage || 'Operation completed successfully'}
                {processedCount !== undefined && totalCount !== undefined && (
                  <span className="block text-xs mt-1">
                    Processed {processedCount} of {totalCount} items
                  </span>
                )}
              </AlertDescription>
            </Alert>
          )}

          {/* Error state */}
          {status === 'failed' && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                {errorMessage || 'Operation failed'}
              </AlertDescription>
            </Alert>
          )}

          {/* Cancelled state */}
          {status === 'cancelled' && (
            <Alert className="border-muted">
              <X className="h-4 w-4" />
              <AlertDescription>
                Operation was cancelled
                {processedCount !== undefined && totalCount !== undefined && (
                  <span className="block text-xs mt-1">
                    {processedCount} of {totalCount} items were processed before cancellation
                  </span>
                )}
              </AlertDescription>
            </Alert>
          )}

          {/* Cancel confirmation */}
          {showCancelConfirm && (
            <Alert className="border-yellow-200 bg-yellow-50 dark:bg-yellow-950/30">
              <AlertTriangle className="h-4 w-4 text-yellow-600" />
              <AlertDescription>
                <div className="space-y-2">
                  <p className="text-yellow-800 dark:text-yellow-200">
                    Are you sure you want to cancel? {Math.round(progress)}% of the operation is already complete.
                  </p>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setShowCancelConfirm(false)}
                    >
                      Continue
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => {
                        setShowCancelConfirm(false)
                        onCancel?.()
                      }}
                    >
                      Yes, Cancel
                    </Button>
                  </div>
                </div>
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>
    )
  }
)
CancellableOperation.displayName = "CancellableOperation"

export { CancellableOperation }
export type { CancellableOperationProps, OperationStatus }
