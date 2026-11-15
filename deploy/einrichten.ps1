# One-time setup of the Google Cloud project for OL-Karten-prep (project.md, decisions 18, 21-23).
# Idempotent where possible: steps that already exist report an error and can be ignored.
# Prerequisites: gcloud auth login, billing (Blaze) enabled.
#   powershell -ExecutionPolicy Bypass -File deploy\einrichten.ps1

$ErrorActionPreference = "Continue"
. "$PSScriptRoot\einstellungen.ps1"

Write-Host "== APIs einschalten"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com `
    firestore.googleapis.com iam.googleapis.com iamcredentials.googleapis.com storage.googleapis.com `
    --project $PROJEKT

Write-Host "== Firestore (Native, $REGION)"
gcloud firestore databases create --location=$REGION --type=firestore-native --project $PROJEKT

Write-Host "== Cloud Storage für die ZIPs (privat, Löschen nach 1 Tag)"
gcloud storage buckets create "gs://$BUCKET" --location=$REGION --uniform-bucket-level-access `
    --public-access-prevention --project $PROJEKT
$lifecycle = Join-Path $env:TEMP "olprep_lifecycle.json"
'{"rule":[{"action":{"type":"Delete"},"condition":{"age":1}}]}' | Out-File -Encoding ascii $lifecycle
gcloud storage buckets update "gs://$BUCKET" --lifecycle-file=$lifecycle

Write-Host "== Artifact Registry für das Container-Image"
gcloud artifacts repositories create $REPO --repository-format=docker --location=$REGION --project $PROJEKT

Write-Host "== Dienstkonto für Service und Job"
gcloud iam service-accounts create $SA_NAME --display-name="OL-Karten-prep Cloud Run" --project $PROJEKT
gcloud projects add-iam-policy-binding $PROJEKT --member="serviceAccount:$SA" --role="roles/datastore.user" --condition=None
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" --member="serviceAccount:$SA" --role="roles/storage.objectAdmin"
# signed download URLs without a key file: the account signs through the IAM API with itself
gcloud iam service-accounts add-iam-policy-binding $SA --member="serviceAccount:$SA" `
    --role="roles/iam.serviceAccountTokenCreator" --project $PROJEKT

Write-Host "Fertig. Danach: deploy\hochladen.ps1 (setzt auch das Recht, den Job zu starten)."
