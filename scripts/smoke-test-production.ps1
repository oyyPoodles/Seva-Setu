param(
  [Parameter(Mandatory = $true)]
  [string]$BackendUrl,

  [Parameter(Mandatory = $true)]
  [string]$FrontendUrl
)

$ErrorActionPreference = "Stop"

function Test-JsonEndpoint {
  param(
    [string]$Name,
    [string]$Url
  )

  Write-Host "Checking $Name -> $Url"
  $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 30
  if ($response.StatusCode -lt 200 -or $response.StatusCode -ge 300) {
    throw "$Name returned HTTP $($response.StatusCode)"
  }
  $response.Content | ConvertFrom-Json | Out-Null
}

function Test-Page {
  param(
    [string]$Name,
    [string]$Url
  )

  Write-Host "Checking $Name -> $Url"
  $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 30
  if ($response.StatusCode -lt 200 -or $response.StatusCode -ge 300) {
    throw "$Name returned HTTP $($response.StatusCode)"
  }
  if ($response.Content.Length -lt 200) {
    throw "$Name returned an unexpectedly small response"
  }
}

$BackendUrl = $BackendUrl.TrimEnd("/")
$FrontendUrl = $FrontendUrl.TrimEnd("/")

Test-JsonEndpoint -Name "backend health" -Url "$BackendUrl/health"
Test-JsonEndpoint -Name "dashboard stats" -Url "$BackendUrl/api/dashboard/stats"
Test-JsonEndpoint -Name "needs list" -Url "$BackendUrl/api/needs?page=1&page_size=5"
Test-Page -Name "frontend home" -Url $FrontendUrl
Test-Page -Name "frontend dashboard" -Url "$FrontendUrl/dashboard"
Test-Page -Name "frontend needs" -Url "$FrontendUrl/needs"

Write-Host "Smoke checks passed."
