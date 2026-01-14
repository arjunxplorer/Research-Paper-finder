# Free Deployment Guide

This guide will help you deploy both the frontend and backend for free.

## 🎯 Overview

- **Frontend (Next.js)**: Deploy on **Vercel** (free tier)
- **Backend (FastAPI)**: Deploy on **Render** (free tier)

## 📋 Prerequisites

1. GitHub account
2. Vercel account (sign up at https://vercel.com)
3. Render account (sign up at https://render.com)

---

## 🚀 Step 1: Push Code to GitHub

1. Initialize git (if not already done):
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   ```

2. Create a new repository on GitHub

3. Push your code:
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   git branch -M main
   git push -u origin main
   ```

---

## 🎨 Step 2: Deploy Frontend on Vercel

1. **Go to Vercel**: https://vercel.com
2. **Sign up/Login** with your GitHub account
3. **Click "Add New Project"**
4. **Import your GitHub repository**
5. **Configure the project**:
   - **Framework Preset**: Next.js (auto-detected)
   - **Root Directory**: `frontend` (important!)
   - **Build Command**: `npm run build` (auto-detected)
   - **Output Directory**: `.next` (auto-detected)
6. **Environment Variables** (add these):
   - `NEXT_PUBLIC_API_URL` = `https://your-backend-url.onrender.com`
     - ⚠️ You'll update this after deploying the backend
7. **Click "Deploy"**

✅ Your frontend will be live at: `https://your-project.vercel.app`

---

## ⚙️ Step 3: Deploy Backend on Render

### Option A: Using Render Dashboard (Recommended)

1. **Go to Render**: https://render.com
2. **Sign up/Login** with your GitHub account
3. **Click "New +" → "Web Service"**
4. **Connect your GitHub repository**
5. **Configure the service**:
   - **Name**: `best-papers-finder-api` (or any name)
   - **Environment**: `Python 3`
   - **Region**: Choose closest to you
   - **Branch**: `main`
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
6. **Environment Variables** (click "Add Environment Variable"):
   - `CORS_ORIGINS` = `https://your-frontend.vercel.app`
     - ⚠️ You'll update this after deploying the frontend
   - `PYTHON_VERSION` = `3.11.0` (optional)
7. **Click "Create Web Service"**

✅ Your backend will be live at: `https://your-service.onrender.com`

### Option B: Using render.yaml (Alternative)

If you prefer, you can use the `render.yaml` file in the `backend/` directory:

1. Go to Render Dashboard
2. Click "New +" → "Blueprint"
3. Connect your repository
4. Render will automatically detect and use `render.yaml`

---

## 🔗 Step 4: Connect Frontend and Backend

After both are deployed:

1. **Update Frontend Environment Variable**:
   - Go to Vercel Dashboard → Your Project → Settings → Environment Variables
   - Update `NEXT_PUBLIC_API_URL` with your Render backend URL
   - Redeploy (Vercel will auto-redeploy or trigger manually)

2. **Update Backend CORS**:
   - Go to Render Dashboard → Your Service → Environment
   - Update `CORS_ORIGINS` with your Vercel frontend URL
   - Render will auto-restart

---

## 🧪 Step 5: Test Your Deployment

1. **Test Backend**: Visit `https://your-backend.onrender.com/health`
   - Should return: `{"status":"healthy"}`

2. **Test Frontend**: Visit `https://your-frontend.vercel.app`
   - Should load your app
   - Try a search query to test the API connection

---

## ⚠️ Important Notes

### Render Free Tier Limitations:
- **Spins down after 15 minutes of inactivity**
- First request after spin-down takes ~30-50 seconds (cold start)
- Subsequent requests are fast
- 750 hours/month free (enough for most projects)

### Vercel Free Tier:
- Unlimited deployments
- Fast CDN
- Automatic HTTPS
- Great for Next.js apps

### Troubleshooting:

**Backend not responding?**
- Check Render logs: Dashboard → Your Service → Logs
- Verify the start command is correct
- Check environment variables

**CORS errors?**
- Make sure `CORS_ORIGINS` in Render includes your Vercel URL
- Check browser console for specific error

**Frontend can't connect to backend?**
- Verify `NEXT_PUBLIC_API_URL` is set correctly in Vercel
- Make sure the backend URL doesn't have a trailing slash
- Check that backend is running (visit `/health` endpoint)

---

## 🎉 You're Done!

Your full-stack application is now live and free!

- Frontend: `https://your-app.vercel.app`
- Backend: `https://your-api.onrender.com`

---

## 📝 Optional: Custom Domains

Both Vercel and Render support custom domains:
- **Vercel**: Settings → Domains
- **Render**: Settings → Custom Domains

---

## 🔄 Updating Your App

Simply push to GitHub:
```bash
git add .
git commit -m "Your changes"
git push
```

Both Vercel and Render will automatically redeploy!
