# SignPath Foundation Application

SignPath Foundation provides free code signing for open-source software.

Application page: https://signpath.org/apply

## Before applying

The following must already be true:

- The GitHub repository is public.
- The repository contains the GPL-3.0 license.
- The `Build Windows` workflow runs on GitHub-hosted runners.
- A recent build completed successfully.
- The source and build scripts are in the repository.
- The release artifact is produced by the workflow.

## Suggested application values

**Project name**

`CCTV Video Downloader`

**Project description**

`A Windows desktop utility that downloads publicly available videos from CCTV video detail pages. It is written in Python and built with PyInstaller on GitHub-hosted Windows runners.`

**Repository URL**

`https://github.com/dinshin110-hub/CCTV-Video-Downloader`

**Maintainer**

`YaoYao`

**License**

`GPL-3.0-only`

**Project category**

`Desktop application / Developer tool`

**Build system**

`GitHub Actions, windows-latest`

**Build command**

`./scripts/build_windows.ps1`

**Artifact**

`CCTVVideoDownloader.exe`

**Signing type**

`Authenticode`

**Signing integration**

`GitHub Actions`

**Artifact root**

`ZIP archive containing CCTVVideoDownloader.exe`

The repository includes the proposed artifact configuration at:

`packaging/artifact-configuration.xml`

## After SignPath approves the project

SignPath will provide the organization ID, project slug, signing policy slug,
artifact configuration slug, and an API token with submitter permissions.

In the GitHub repository, create these repository variables:

- `SIGNPATH_ENABLED=true`
- `SIGNPATH_ORGANIZATION_ID`
- `SIGNPATH_PROJECT_SLUG`
- `SIGNPATH_SIGNING_POLICY_SLUG`
- `SIGNPATH_ARTIFACT_CONFIGURATION_SLUG`

Create this repository secret:

- `SIGNPATH_API_TOKEN`

Then create and push a version tag:

```powershell
git tag v1.0.1
git push origin v1.0.1
```

The `Release` workflow will submit the unsigned EXE to SignPath, wait for the
signed artifact, and publish it to GitHub Releases.
