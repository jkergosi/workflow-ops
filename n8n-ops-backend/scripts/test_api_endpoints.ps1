# API Endpoint Testing Script (PowerShell)
# Tests the /billing/plan-features/all endpoint

param(
    [string]$BaseUrl = "http://localhost:8000"
)

$endpoint = "$BaseUrl/api/v1/billing/plan-features/all"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Testing API Endpoint: $endpoint" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Test 2.1: Endpoint Response Structure
Write-Host "Test 2.1: Endpoint Response Structure" -ForegroundColor Yellow
Write-Host "--------------------------------------" -ForegroundColor Yellow

try {
    $response = Invoke-RestMethod -Uri $endpoint -Method Get -ErrorAction Stop
    $statusCode = 200
    
    Write-Host "HTTP Status: $statusCode" -ForegroundColor Green
    Write-Host "[PASS] Status: 200 OK" -ForegroundColor Green
    
    # Check if response is a dictionary
    if ($response -is [hashtable] -or $response -is [PSCustomObject]) {
        Write-Host "[PASS] Response is a dictionary" -ForegroundColor Green
        
        # Check for expected plans
        $plans = $response.PSObject.Properties.Name
        Write-Host "Plans found: $($plans -join ', ')" -ForegroundColor Cyan
        
        $expectedPlans = @("free", "pro", "agency", "enterprise")
        $foundPlans = $plans | Where-Object { $expectedPlans -contains $_ }
        
        if ($foundPlans.Count -gt 0) {
            Write-Host "[PASS] Response includes expected plans" -ForegroundColor Green
        } else {
            Write-Host "[WARN] Response does not include expected plans" -ForegroundColor Yellow
        }
        
        # Check for features in each plan
        $hasFeatures = $false
        $hasFlag = $false
        $hasLimit = $false
        
        foreach ($plan in $plans) {
            $planFeatures = $response.$plan
            if ($planFeatures -is [hashtable] -or $planFeatures -is [PSCustomObject]) {
                $featureCount = ($planFeatures.PSObject.Properties | Measure-Object).Count
                if ($featureCount -gt 0) {
                    $hasFeatures = $true
                    Write-Host "[PASS] $plan`: $featureCount features" -ForegroundColor Green
                    
                    # Check for flag and limit features
                    foreach ($featureName in $planFeatures.PSObject.Properties.Name) {
                        $featureValue = $planFeatures.$featureName
                        if ($featureValue -is [bool]) {
                            $hasFlag = $true
                        } elseif ($featureValue -is [int] -or $featureValue -is [double]) {
                            $hasLimit = $true
                        }
                    }
                } else {
                    Write-Host "[WARN] $plan`: No features (may indicate empty plan_features table)" -ForegroundColor Yellow
                }
            }
        }
        
        if ($hasFeatures) {
            Write-Host "[PASS] Response includes feature mappings" -ForegroundColor Green
        } else {
            Write-Host "[WARN] Response has empty feature mappings" -ForegroundColor Yellow
        }
        
        if ($hasFlag) {
            Write-Host "[PASS] Flag features present (boolean values)" -ForegroundColor Green
        } else {
            Write-Host "[WARN] No flag features found" -ForegroundColor Yellow
        }
        
        if ($hasLimit) {
            Write-Host "[PASS] Limit features present (numeric values)" -ForegroundColor Green
        } else {
            Write-Host "[WARN] No limit features found" -ForegroundColor Yellow
        }
        
    } else {
        Write-Host "[FAIL] Response is not a dictionary" -ForegroundColor Red
    }
    
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    if ($statusCode) {
        Write-Host "HTTP Status: $statusCode" -ForegroundColor Red
        Write-Host "[FAIL] Endpoint returned $statusCode" -ForegroundColor Red
    } else {
        Write-Host "[FAIL] Cannot connect to endpoint" -ForegroundColor Red
        Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "Make sure the backend server is running on port 8000" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Test Complete" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

