# GitHub + Tencent COS Deploy

This repository uses GitHub as the source of truth and Tencent Cloud COS as the China-friendly public hosting target.

## Flow

1. Edit the local gallery source in `workspace/`.
2. Refresh the public static snapshot in `docs/`.
3. Commit and push to `main`.
4. GitHub Actions runs tests.
5. GitHub Actions uploads `docs/` to Tencent COS bucket `personal-brain-gallery-1441292354` in `ap-guangzhou`.

## Required GitHub Secrets

Add these repository secrets in GitHub:

- `TENCENT_CLOUD_SECRET_ID`
- `TENCENT_CLOUD_SECRET_KEY`

Use a Tencent Cloud CAM sub-user or role with the minimum permission needed to upload objects to this COS bucket. Do not commit the key into the repository.

## Public COS URLs

After a successful workflow run, the public entry should be:

```text
https://personal-brain-gallery-1441292354.cos.ap-guangzhou.myqcloud.com/index.html
```

If static website hosting is enabled in COS, the bucket website endpoint can serve `index.html` as the default page.

## Local Refresh Command

```bash
cp workspace/personal-brain-gallery.html docs/index.html
cp workspace/personal-brain-exhibits.json docs/personal-brain-exhibits.json
cp workspace/brain-dashboard-data.json docs/brain-dashboard-data.json
```
