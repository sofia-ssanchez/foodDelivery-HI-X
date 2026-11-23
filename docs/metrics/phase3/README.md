# Phase III SonarQube Cloud baseline

## Baseline and configuration

| Item | Value |
|---|---|
| Tool | SonarQube Cloud |
| Scanner | SonarScanner for Python (`pysonar`) 1.11.0.6012 |
| Baseline tag | `phase3` |
| Baseline source commit | `e52ee101250eea29831c1bab1bfa957a3fc5c025` (`e52ee10`) |
| SonarQube project key | `five-leaf-clover-soen-343` |

Git resolves `phase3` to `e52ee10`. The baseline-export commit `7f858437` adds only the two JSON exports and this scanner configuration; its parent has the same source tree as `phase3`. The JSON response itself identifies the SonarQube project, but does not store the analyzed Git SHA.

The scanner configuration is [`sonar-project.properties`](sonar-project.properties):

- Sources: `backend,frontend/src`
- Exclusions: `**/migrations/**`, `**/__pycache__/**`, `**/node_modules/**`, `**/.next/**`, `**/.venv/**`, `**/venv/**`, `**/db.sqlite3`
- Source encoding: UTF-8
- Organization: `fooddelivery-hi-x`

Keep this file, scanner version, project key, and analysis settings the same for `phase4-refactored` and `phase4` so the measurements can be compared.

## Export files

- [`file_metrics.json`](file_metrics.json) contains SonarQube Cloud component/file measures. The metric keys are `ncloc` (non-comment lines of code), `complexity` (Sonar's cyclomatic complexity measure), and `cognitive_complexity`.
- [`issues.json`](issues.json) contains the SonarQube-reported issue records, including rule, type, severity, affected component, message, and remediation effort. Code smells are the records whose issue `type` is `CODE_SMELL`.

The exports are file-level. They do not provide a per-class metric breakdown or the assignment's manual class-coupling counts.

## Reproducing the measurements and exports

Use a clean checkout of the target tag and the same scanner and properties file for each snapshot. A SonarQube Cloud token with permission to analyze the project is required; set it locally as `SONAR_TOKEN` using a secure secret store. Never put the token in this file, a properties file, or a committed script.

```bash
git switch --detach phase3
python -m pip install "pysonar==1.11.0.6012"
# Set SONAR_TOKEN in the local environment without adding its value to the repository.
pysonar
```

After the analysis completes, export the per-file measures and issue list from SonarQube Cloud's Web API. These examples write to temporary files; review the responses before replacing committed exports.

```bash
curl --fail --silent --show-error --get \
  --url 'https://sonarcloud.io/api/measures/component_tree' \
  --header "Authorization: Bearer ${SONAR_TOKEN}" \
  --data-urlencode 'component=five-leaf-clover-soen-343' \
  --data-urlencode 'metricKeys=ncloc,complexity,cognitive_complexity' \
  --data-urlencode 'ps=500' \
  --output /tmp/file_metrics.json

curl --fail --silent --show-error --get \
  --url 'https://sonarcloud.io/api/issues/search' \
  --header "Authorization: Bearer ${SONAR_TOKEN}" \
  --data-urlencode 'componentKeys=five-leaf-clover-soen-343' \
  --data-urlencode 'p=1' \
  --data-urlencode 'ps=500' \
  --output /tmp/issues.json
```

The SonarQube Cloud Web API and PySonar scanner documentation describe authentication and metric extraction: [Web API](https://docs.sonarsource.com/sonarqube-cloud/appendices/web-api) and [SonarScanner for Python](https://docs.sonarsource.com/sonarqube-cloud/analyzing-source-code/scanners/sonarscanner-for-python).

For later snapshots, check out `phase4-refactored` and `phase4` in turn, analyze each with the same scanner version and configuration, and retain the corresponding exports under `docs/metrics/phase4-refactored/` and `docs/metrics/phase4/`. The Phase IV instructions explicitly require the Phase IV output under `docs/metrics/phase4/`.

## Phase IV baseline checklist

The committed exports document file-level LOC, cyclomatic complexity, cognitive complexity, and reported issues/code smells. They are the raw SonarQube Cloud output for this baseline.

The Phase IV report still needs the five-hotspot table and justification, including each hotspot's named code smell and the optional module it makes harder to add. The assignment also requires manual class-coupling counts for those five hotspots. These analyses are not present in the JSON exports and are not claimed complete here. Class-level metrics must also be supplied if required for the selected hotspot classes; this export is file-level.

For Phase IV, add the `phase4-refactored` and `phase4` measurement outputs and the required three-snapshot comparison. The repository README must also explain how to run the characterization tests.
