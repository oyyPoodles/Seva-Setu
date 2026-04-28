param(
  [Parameter(Mandatory = $true)]
  [string]$ProjectId,

  [string]$Region = "asia-south1",
  [string]$ServiceName = "sevasetu-backend",
  [string]$SqlInstanceName = "sevasetu-postgres",
  [string]$DatabaseName = "sevasetu",
  [string]$DatabaseUser = "postgres",
  [string]$FrontendUrl = "",
  [string]$GeminiApiKey = "",
  [string]$GoogleMapsApiKey = "",
  [string]$DatabasePassword = ""
)

$ErrorActionPreference = "Stop"

function Require-Command {
  param([string]$Name)
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "$Name is not installed or is not on PATH."
  }
}

function Read-SecretValue {
  param([string]$Prompt)
  $secure = Read-Host $Prompt -AsSecureString
  $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  try {
    [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
  } finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
  }
}

function Set-GcpSecret {
  param(
    [string]$Name,
    [string]$Value
  )

  gcloud secrets describe $Name --project $ProjectId *> $null
  if ($LASTEXITCODE -ne 0) {
    gcloud secrets create $Name --project $ProjectId --replication-policy automatic
  }

  $tmp = New-TemporaryFile
  try {
    Set-Content -LiteralPath $tmp.FullName -Value $Value -NoNewline
    gcloud secrets versions add $Name --project $ProjectId --data-file $tmp.FullName
  } finally {
    Remove-Item -LiteralPath $tmp.FullName -Force
  }
}

Require-Command gcloud
Require-Command firebase

if (-not $FrontendUrl) {
  $FrontendUrl = "https://$ProjectId.web.app"
}
if (-not $DatabasePassword) {
  $DatabasePassword = Read-SecretValue "Cloud SQL password for user '$DatabaseUser'"
}
if (-not $GeminiApiKey) {
  $GeminiApiKey = Read-SecretValue "Gemini API key"
}
if (-not $GoogleMapsApiKey) {
  $GoogleMapsApiKey = Read-SecretValue "Google Maps API key"
}

gcloud config set project $ProjectId

gcloud services enable `
  run.googleapis.com `
  sqladmin.googleapis.com `
  cloudbuild.googleapis.com `
  artifactregistry.googleapis.com `
  secretmanager.googleapis.com `
  firebase.googleapis.com `
  firebasehosting.googleapis.com `
  --project $ProjectId

# If this is a plain Google Cloud project, attach Firebase resources to it.
# The command is harmless for projects that are already Firebase projects.
firebase projects:addfirebase $ProjectId --non-interactive *> $null

gcloud sql instances describe $SqlInstanceName --project $ProjectId *> $null
if ($LASTEXITCODE -ne 0) {
  gcloud sql instances create $SqlInstanceName `
    --project $ProjectId `
    --region $Region `
    --database-version POSTGRES_16 `
    --tier db-custom-1-3840 `
    --storage-size 20GB `
    --storage-type SSD `
    --availability-type zonal `
    --backup-start-time 02:00
}

gcloud sql users set-password $DatabaseUser `
  --project $ProjectId `
  --instance $SqlInstanceName `
  --password $DatabasePassword

gcloud sql databases describe $DatabaseName --instance $SqlInstanceName --project $ProjectId *> $null
if ($LASTEXITCODE -ne 0) {
  gcloud sql databases create $DatabaseName --instance $SqlInstanceName --project $ProjectId
}

$ConnectionName = gcloud sql instances describe $SqlInstanceName --project $ProjectId --format "value(connectionName)"
$EscapedPassword = [Uri]::EscapeDataString($DatabasePassword)
$DatabaseUrl = "postgresql+asyncpg://$DatabaseUser`:$EscapedPassword@/$DatabaseName`?host=/cloudsql/$ConnectionName"

Set-GcpSecret -Name "sevasetu-database-url" -Value $DatabaseUrl
Set-GcpSecret -Name "sevasetu-gemini-api-key" -Value $GeminiApiKey
Set-GcpSecret -Name "sevasetu-google-maps-api-key" -Value $GoogleMapsApiKey

$ProjectNumber = gcloud projects describe $ProjectId --format "value(projectNumber)"
$RunServiceAccount = "$ProjectNumber-compute@developer.gserviceaccount.com"

gcloud projects add-iam-policy-binding $ProjectId `
  --member "serviceAccount:$RunServiceAccount" `
  --role "roles/cloudsql.client" `
  --quiet

gcloud projects add-iam-policy-binding $ProjectId `
  --member "serviceAccount:$RunServiceAccount" `
  --role "roles/secretmanager.secretAccessor" `
  --quiet

gcloud run deploy $ServiceName `
  --project $ProjectId `
  --region $Region `
  --source backend `
  --port 8000 `
  --allow-unauthenticated `
  --add-cloudsql-instances $ConnectionName `
  --set-env-vars "APP_ENV=production,APP_VERSION=0.1.0,LOG_LEVEL=INFO,GOOGLE_CLOUD_PROJECT=$ProjectId,FRONTEND_URL=$FrontendUrl,FIREBASE_DEV_BYPASS=false" `
  --set-secrets "DATABASE_URL=sevasetu-database-url:latest,GEMINI_API_KEY=sevasetu-gemini-api-key:latest,GOOGLE_MAPS_API_KEY=sevasetu-google-maps-api-key:latest" `
  --min-instances 1 `
  --max-instances 10 `
  --cpu 2 `
  --memory 4Gi `
  --timeout 300 `
  --quiet

$BackendUrl = gcloud run services describe $ServiceName --project $ProjectId --region $Region --format "value(status.url)"
$WsUrl = $BackendUrl -replace "^https:", "wss:"

Set-Content -LiteralPath "frontend\.env.production" -Value @"
NEXT_PUBLIC_API_URL=$BackendUrl
NEXT_PUBLIC_WS_URL=$WsUrl
"@

Set-Content -LiteralPath ".firebaserc" -Value @"
{
  "projects": {
    "production": "$ProjectId"
  }
}
"@

firebase experiments:enable webframeworks *> $null
firebase deploy --only hosting --project $ProjectId

Write-Host ""
Write-Host "Production deployment complete."
Write-Host "Backend:  $BackendUrl"
Write-Host "Frontend: $FrontendUrl"
Write-Host "Health:   $BackendUrl/health"
