# Shared settings of the deploy scripts (no secrets in here: the repository is public).
$PROJEKT = "ol-karten-prep"
$REGION  = "europe-west1"                      # decision 23
$BUCKET  = "ol-karten-prep-ergebnisse"         # ZIPs, deleted after 1 day
$REPO    = "olprep"                            # Artifact Registry (Docker)
$SERVICE = "olprep-api"                        # Cloud Run service: API
$JOB     = "olprep-auftrag"                    # Cloud Run job: builds one map
$SA_NAME = "olprep-runner"
$SA      = "$SA_NAME@$PROJEKT.iam.gserviceaccount.com"
