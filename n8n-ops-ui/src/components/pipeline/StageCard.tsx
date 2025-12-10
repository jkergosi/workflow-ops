import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { ChevronDown, ChevronUp } from 'lucide-react';
import type {
  PipelineStage,
  RiskLevel,
  ApprovalType,
  Environment,
} from '@/types';

interface StageCardProps {
  stage: PipelineStage;
  sourceEnv: Environment | undefined;
  targetEnv: Environment | undefined;
  onChange: (stage: PipelineStage) => void;
}

export function StageCard({
  stage,
  sourceEnv,
  targetEnv,
  onChange,
}: StageCardProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  const updateStage = (updates: Partial<PipelineStage>) => {
    onChange({ ...stage, ...updates });
  };

  const updateGates = (updates: Partial<PipelineStage['gates']>) => {
    updateStage({
      gates: { ...stage.gates, ...updates },
    });
  };

  const updateApprovals = (updates: Partial<PipelineStage['approvals']>) => {
    updateStage({
      approvals: { ...stage.approvals, ...updates },
    });
  };

  const updateSchedule = (updates: Partial<NonNullable<PipelineStage['schedule']>>) => {
    updateStage({
      schedule: { ...stage.schedule, ...updates },
    });
  };

  const updatePolicyFlags = (updates: Partial<PipelineStage['policyFlags']>) => {
    updateStage({
      policyFlags: { ...stage.policyFlags, ...updates },
    });
  };

  const daysOfWeek = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

  return (
    <Card>
      <CardHeader
        className="cursor-pointer hover:bg-muted/50 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              {sourceEnv?.name || 'Source'} → {targetEnv?.name || 'Target'}
            </CardTitle>
            <CardDescription>Configure promotion rules for this stage</CardDescription>
          </div>
          {isExpanded ? (
            <ChevronUp className="h-5 w-5 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-5 w-5 text-muted-foreground" />
          )}
        </div>
      </CardHeader>
      {isExpanded && (
        <CardContent className="space-y-6">
          {/* Basic Info - Read Only */}
          <div className="space-y-4 pb-4 border-b">
            <h4 className="font-semibold">Basic Info</h4>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Source Environment</Label>
                <Input value={sourceEnv?.name || 'N/A'} disabled className="bg-muted" />
              </div>
              <div>
                <Label>Target Environment</Label>
                <Input value={targetEnv?.name || 'N/A'} disabled className="bg-muted" />
              </div>
            </div>
          </div>

          {/* Gates */}
          <div className="space-y-4 pb-4 border-b">
            <h4 className="font-semibold">Gates</h4>
            <div className="space-y-3">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id={`gates-clean-drift-${stage.sourceEnvironmentId}`}
                  checked={stage.gates.requireCleanDrift}
                  onCheckedChange={(checked) =>
                    updateGates({ requireCleanDrift: checked === true })
                  }
                />
                <Label
                  htmlFor={`gates-clean-drift-${stage.sourceEnvironmentId}`}
                  className="cursor-pointer"
                >
                  Require clean drift before promotion
                </Label>
              </div>
              <div className="flex items-center space-x-2">
                <Checkbox
                  id={`gates-preflight-${stage.sourceEnvironmentId}`}
                  checked={stage.gates.runPreFlightValidation}
                  onCheckedChange={(checked) => {
                    const isChecked = checked === true;
                    updateGates({
                      runPreFlightValidation: isChecked,
                      credentialsExistInTarget: isChecked ? stage.gates.credentialsExistInTarget : false,
                      nodesSupportedInTarget: isChecked ? stage.gates.nodesSupportedInTarget : false,
                      webhooksAvailable: isChecked ? stage.gates.webhooksAvailable : false,
                    });
                  }}
                />
                <Label
                  htmlFor={`gates-preflight-${stage.sourceEnvironmentId}`}
                  className="cursor-pointer"
                >
                  Run pre-flight validation
                </Label>
              </div>
              {stage.gates.runPreFlightValidation && (
                <div className="ml-6 space-y-2">
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id={`gates-credentials-${stage.sourceEnvironmentId}`}
                      checked={stage.gates.credentialsExistInTarget}
                      onCheckedChange={(checked) =>
                        updateGates({ credentialsExistInTarget: checked === true })
                      }
                    />
                    <Label
                      htmlFor={`gates-credentials-${stage.sourceEnvironmentId}`}
                      className="cursor-pointer text-sm"
                    >
                      Credentials exist in target
                    </Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id={`gates-nodes-${stage.sourceEnvironmentId}`}
                      checked={stage.gates.nodesSupportedInTarget}
                      onCheckedChange={(checked) =>
                        updateGates({ nodesSupportedInTarget: checked === true })
                      }
                    />
                    <Label
                      htmlFor={`gates-nodes-${stage.sourceEnvironmentId}`}
                      className="cursor-pointer text-sm"
                    >
                      Nodes supported in target
                    </Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id={`gates-webhooks-${stage.sourceEnvironmentId}`}
                      checked={stage.gates.webhooksAvailable}
                      onCheckedChange={(checked) =>
                        updateGates({ webhooksAvailable: checked === true })
                      }
                    />
                    <Label
                      htmlFor={`gates-webhooks-${stage.sourceEnvironmentId}`}
                      className="cursor-pointer text-sm"
                    >
                      Webhooks available
                    </Label>
                  </div>
                </div>
              )}
              <div className="flex items-center space-x-2">
                <Checkbox
                  id={`gates-healthy-${stage.sourceEnvironmentId}`}
                  checked={stage.gates.targetEnvironmentHealthy}
                  onCheckedChange={(checked) =>
                    updateGates({ targetEnvironmentHealthy: checked === true })
                  }
                />
                <Label
                  htmlFor={`gates-healthy-${stage.sourceEnvironmentId}`}
                  className="cursor-pointer"
                >
                  Target environment must be Healthy
                </Label>
              </div>
              <div className="space-y-2">
                <Label htmlFor={`gates-risk-${stage.sourceEnvironmentId}`}>
                  Max allowed workflow risk level
                </Label>
                <Select
                  value={stage.gates.maxAllowedRiskLevel}
                  onValueChange={(value: RiskLevel) =>
                    updateGates({ maxAllowedRiskLevel: value })
                  }
                >
                  <SelectTrigger id={`gates-risk-${stage.sourceEnvironmentId}`}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Low">Low</SelectItem>
                    <SelectItem value="Medium">Medium</SelectItem>
                    <SelectItem value="High">High</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          {/* Approvals */}
          <div className="space-y-4 pb-4 border-b">
            <h4 className="font-semibold">Approvals</h4>
            <div className="space-y-3">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id={`approvals-require-${stage.sourceEnvironmentId}`}
                  checked={stage.approvals.requireApproval}
                  onCheckedChange={(checked) =>
                    updateApprovals({ requireApproval: checked === true })
                  }
                />
                <Label
                  htmlFor={`approvals-require-${stage.sourceEnvironmentId}`}
                  className="cursor-pointer"
                >
                  Require approval
                </Label>
              </div>
              {stage.approvals.requireApproval && (
                <div className="ml-6 space-y-3">
                  <div className="space-y-2">
                    <Label htmlFor={`approvals-role-${stage.sourceEnvironmentId}`}>
                      Approver role/group
                    </Label>
                    <Input
                      id={`approvals-role-${stage.sourceEnvironmentId}`}
                      value={stage.approvals.approverRole || ''}
                      onChange={(e) => updateApprovals({ approverRole: e.target.value })}
                      placeholder="admin, developer, etc."
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor={`approvals-type-${stage.sourceEnvironmentId}`}>
                      Required approvals
                    </Label>
                    <Select
                      value={stage.approvals.requiredApprovals || '1 of N'}
                      onValueChange={(value: ApprovalType) =>
                        updateApprovals({ requiredApprovals: value })
                      }
                    >
                      <SelectTrigger id={`approvals-type-${stage.sourceEnvironmentId}`}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="1 of N">1 of N</SelectItem>
                        <SelectItem value="All">All</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Schedule Restrictions */}
          <div className="space-y-4 pb-4 border-b">
            <h4 className="font-semibold">Schedule Restrictions</h4>
            <div className="space-y-3">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id={`schedule-restrict-${stage.sourceEnvironmentId}`}
                  checked={stage.schedule?.restrictPromotionTimes || false}
                  onCheckedChange={(checked) => {
                    if (checked) {
                      updateSchedule({
                        restrictPromotionTimes: true,
                        allowedDays: [],
                        startTime: '09:00',
                        endTime: '17:00',
                      });
                    } else {
                      updateSchedule({ restrictPromotionTimes: false });
                    }
                  }}
                />
                <Label
                  htmlFor={`schedule-restrict-${stage.sourceEnvironmentId}`}
                  className="cursor-pointer"
                >
                  Restrict promotion times
                </Label>
              </div>
              {stage.schedule?.restrictPromotionTimes && (
                <div className="ml-6 space-y-3">
                  <div className="space-y-2">
                    <Label>Allowed days</Label>
                    <div className="grid grid-cols-2 gap-2">
                      {daysOfWeek.map((day) => (
                        <div key={day} className="flex items-center space-x-2">
                          <Checkbox
                            id={`schedule-day-${day}-${stage.sourceEnvironmentId}`}
                            checked={stage.schedule?.allowedDays?.includes(day) || false}
                            onCheckedChange={(checked) => {
                              const currentDays = stage.schedule?.allowedDays || [];
                              const newDays = checked
                                ? [...currentDays, day]
                                : currentDays.filter((d) => d !== day);
                              updateSchedule({ allowedDays: newDays });
                            }}
                          />
                          <Label
                            htmlFor={`schedule-day-${day}-${stage.sourceEnvironmentId}`}
                            className="cursor-pointer text-sm"
                          >
                            {day}
                          </Label>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor={`schedule-start-${stage.sourceEnvironmentId}`}>
                        Start time
                      </Label>
                      <Input
                        id={`schedule-start-${stage.sourceEnvironmentId}`}
                        type="time"
                        value={stage.schedule?.startTime || '09:00'}
                        onChange={(e) => updateSchedule({ startTime: e.target.value })}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor={`schedule-end-${stage.sourceEnvironmentId}`}>
                        End time
                      </Label>
                      <Input
                        id={`schedule-end-${stage.sourceEnvironmentId}`}
                        type="time"
                        value={stage.schedule?.endTime || '17:00'}
                        onChange={(e) => updateSchedule({ endTime: e.target.value })}
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Policy Flags */}
          <div className="space-y-4">
            <h4 className="font-semibold">Policy Flags</h4>
            <div className="space-y-3">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id={`policy-placeholder-${stage.sourceEnvironmentId}`}
                  checked={stage.policyFlags.allowPlaceholderCredentials}
                  onCheckedChange={(checked) =>
                    updatePolicyFlags({ allowPlaceholderCredentials: checked === true })
                  }
                />
                <Label
                  htmlFor={`policy-placeholder-${stage.sourceEnvironmentId}`}
                  className="cursor-pointer"
                >
                  Allow placeholder credentials in target
                </Label>
              </div>
              <div className="flex items-center space-x-2">
                <Checkbox
                  id={`policy-hotfix-${stage.sourceEnvironmentId}`}
                  checked={stage.policyFlags.allowOverwritingHotfixes}
                  onCheckedChange={(checked) =>
                    updatePolicyFlags({ allowOverwritingHotfixes: checked === true })
                  }
                />
                <Label
                  htmlFor={`policy-hotfix-${stage.sourceEnvironmentId}`}
                  className="cursor-pointer"
                >
                  Allow overwriting target hotfixes
                </Label>
              </div>
              <div className="flex items-center space-x-2">
                <Checkbox
                  id={`policy-force-${stage.sourceEnvironmentId}`}
                  checked={stage.policyFlags.allowForcePromotionOnConflicts}
                  onCheckedChange={(checked) =>
                    updatePolicyFlags({ allowForcePromotionOnConflicts: checked === true })
                  }
                />
                <Label
                  htmlFor={`policy-force-${stage.sourceEnvironmentId}`}
                  className="cursor-pointer"
                >
                  Allow force promotion on conflicts
                </Label>
              </div>
            </div>
          </div>
        </CardContent>
      )}
    </Card>
  );
}

