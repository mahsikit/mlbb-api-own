# Deploying to GitHub + Vercel

## 1. Push to GitHub

```bash
cd /path/to/mlbb-api-own
git init
git add .
git commit -m "initial: mlbb api proxy"
# Create a new repo on github.com first, then:
git remote add origin https://github.com/YOUR_USERNAME/mlbb-api-own.git
git push -u origin main
```

## 2. Deploy on Vercel

1. Go to https://vercel.com/new
2. Import your GitHub repo (`mlbb-api-own`)
3. Framework: **Other** (not Next.js)
4. Root directory: leave as `/`
5. Build & output settings: leave defaults (Vercel auto-detects `vercel.json`)
6. Add environment variables (click "Environment Variables"):
   - `AUTH_BASE` = `https://sg-api.mobilelegends.com`
   - `STATS_BASE` = *(leave empty until you find it)*
7. Click **Deploy**

## 3. Test the deployment

Once deployed, your API is at `https://your-project.vercel.app`.

Test it:
```bash
# 1. Send verification code
curl -X POST https://your-project.vercel.app/api/user/auth/send-vc \
  -H "Content-Type: application/json" \
  -d '{"role_id": 742039794, "zone_id": 10382}'

# 2. Login with the code you received in-game
curl -X POST https://your-project.vercel.app/api/user/auth/login \
  -H "Content-Type: application/json" \
  -d '{"role_id": 742039794, "zone_id": 10382, "vc": "1234"}'

# 3. Get your profile (use jwt from login response)
curl -X POST https://your-project.vercel.app/api/user/info \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt>" \
  -d '{"role_id": 742039794, "zone_id": 10382}'
```

Or visit `https://your-project.vercel.app/docs` for interactive testing.

## 4. Add STATS_BASE later

Once you find the STATS_BASE URL (see docs/context.md for how):
1. Go to your Vercel project → Settings → Environment Variables
2. Add `STATS_BASE` = `https://your-stats-host`
3. Redeploy (Vercel → Deployments → redeploy latest)

## Notes

- Vercel free tier has a 10s execution timeout for serverless functions.
  If upstream MLBB calls are slow, you may hit this. Consider adding a 8s timeout
  in `app/core/http.py` if that happens.
- Vercel cold starts add ~500ms to the first request after idle.
- `vercel.json` routes all `/*` to `prod/index.py`, so `/docs`, `/api/*`,
  and `/` all work correctly.
