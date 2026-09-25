# ShipSafe AI

### Agentic Release & Regression Guardian

ShipSafe AI is an agentic developer workflow designed to analyze software changes before release. It investigates code impact, regression-test gaps, security risks, API/requirement mismatches, and database migration risks, then coordinates remediation and validation through IBM Bob 2.0.

## Problem

A seemingly small code change can affect multiple parts of a software system. Developers often have to manually trace dependencies, inspect tests, compare requirements, check APIs, review database changes, and validate the release before deployment.

This process is time-consuming and can miss hidden regression risks.

## Solution

ShipSafe AI turns release validation into an evidence-based agentic workflow.

A release change is analyzed across:

- Architecture and change impact
- Regression test coverage
- Security
- API and requirement compliance
- Database migrations

The findings are synthesized into a release-readiness report. Confirmed issues can then be remediated and validated through another analysis cycle.

## Built With

- IBM Bob 2.0
- Python
- Flask
- SQLite
- Pytest
- Git
- HTML
- CSS
- JavaScript

## Project Status

🚧 Hackathon development in progress.

## Team

Ctrl Alt Solo

## License

MIT License
