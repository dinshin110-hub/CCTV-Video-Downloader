# GitHub Setup

The project is ready to be uploaded as a public GitHub repository.

## 1. Create the repository

Create a public repository named:

`CCTV-Video-Downloader`

Do not initialize it with a README if you plan to push this prepared directory,
or use GitHub's empty repository option.

## 2. Configure Git locally

Replace the name and email with the public Git identity you want to use.

```powershell
cd work\CCTV-Video-Downloader
git init -b main
git config user.name "YaoYao"
git config user.email "<YOUR_GITHUB_NOREPLY_EMAIL>"
git add .
git commit -m "Initial open-source release"
```

## 3. Push to GitHub

```powershell
git remote add origin https://github.com/dinshin110-hub/CCTV-Video-Downloader.git
git push -u origin main
```

## 4. Verify the public build

Open the repository's **Actions** tab and run the `Build Windows` workflow.

A successful workflow must produce:

`CCTVVideoDownloader.exe`

The repository must remain public for the SignPath Foundation open-source
program.

## 5. Create the first tag

After the workflow succeeds:

```powershell
git tag v1.0.0
git push origin v1.0.0
```

At this point the Release workflow creates an unsigned GitHub Release unless
SignPath has been configured. After SignPath approval, it will create a signed
release instead.

## 6. Apply to SignPath

Follow [SIGNPATH_APPLICATION.md](SIGNPATH_APPLICATION.md).
