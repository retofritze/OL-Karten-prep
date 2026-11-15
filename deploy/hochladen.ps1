# Build the container and deploy job, service and Firebase Hosting (each new version).
#   powershell -ExecutionPolicy Bypass -File deploy\hochladen.ps1
# Run the tests before (pytest; after larger changes also pytest -m netz).

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\einstellungen.ps1"
Set-Location (Split-Path $PSScriptRoot -Parent)

function Pruefen([string]$schritt) {
    # Windows PowerShell 5.1 does not stop on errors of external programs: check the exit code
    if ($LASTEXITCODE -ne 0) { throw "Abgebrochen: $schritt (Exit-Code $LASTEXITCODE)" }
}

$tag = (git rev-parse --short HEAD)
if (git status --porcelain) { $tag = "$tag-lokal" }        # uncommitted changes in the image
$IMAGE = "$REGION-docker.pkg.dev/$PROJEKT/$REPO/app:$tag"

Write-Host "== Image bauen (Cloud Build): $IMAGE"
gcloud builds submit --tag $IMAGE --project $PROJEKT --region $REGION .
Pruefen "Image bauen"

Write-Host "== Job $JOB (baut eine Karte; 4 GB gemessen: Spitze 1,7 GB + Dateien in /tmp)"
gcloud run jobs deploy $JOB --image $IMAGE --region $REGION --project $PROJEKT `
    --service-account $SA --memory 4Gi --cpu 2 --task-timeout 30m --max-retries 0 `
    --command python --args="-m,api.job" `
    --set-env-vars "OLPREP_BUCKET=$BUCKET"
Pruefen "Job"
# the API service may start the job with its own AUFTRAG_ID
gcloud run jobs add-iam-policy-binding $JOB --region $REGION --project $PROJEKT `
    --member="serviceAccount:$SA" --role="roles/run.jobsExecutorWithOverrides" | Out-Null
Pruefen "Recht zum Starten des Jobs"

Write-Host "== Service $SERVICE (API, öffentlich)"
gcloud run deploy $SERVICE --image $IMAGE --region $REGION --project $PROJEKT `
    --service-account $SA --allow-unauthenticated --memory 1Gi --cpu 1 `
    --min-instances 0 --max-instances 2 `
    --set-env-vars "OLPREP_BETRIEB=cloud,OLPREP_PROJEKT=$PROJEKT,OLPREP_REGION=$REGION,OLPREP_JOB=$JOB,OLPREP_BUCKET=$BUCKET"
Pruefen "Service"

Write-Host "== Firebase Hosting und Firestore-Regeln"
firebase deploy --only "hosting,firestore:rules" --project $PROJEKT
Pruefen "Firebase"

Write-Host "Fertig: https://$PROJEKT.web.app"
