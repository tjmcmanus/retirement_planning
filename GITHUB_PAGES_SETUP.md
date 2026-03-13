# GitHub Pages Setup - Quick Start

This document provides a quick reference for setting up your Financial Planner documentation on GitHub Pages with the Architect theme.

## What Has Been Created

Your repository now includes a complete GitHub Pages site with:

### Core Files

✅ **`_config.yml`** - Jekyll configuration with Architect theme
✅ **`index.md`** - Professional home page with feature overview
✅ **`Gemfile`** - Ruby dependencies for Jekyll
✅ **`.github/workflows/jekyll.yml`** - Automated deployment workflow
✅ **`DEPLOYMENT.md`** - Comprehensive deployment guide

### Documentation Structure

```
docs/
├── getting-started.md      # Installation and setup guide
├── features.md             # Complete feature documentation
├── guides.md               # User guide index
├── api-reference.md        # Technical API documentation
├── guides/                 # Detailed user guides (to be created)
├── advanced/               # Advanced topics
│   └── betr-guide.md      # BETR Roth conversion guide
└── technical/              # Technical documentation (to be created)
```

## Quick Deployment (3 Steps)

### Step 1: Push to GitHub

```bash
# If not already initialized
git init
git add .
git commit -m "Add GitHub Pages documentation site"

# Add your repository
git remote add origin https://github.com/YOUR_USERNAME/retirement_planning.git

# Push to GitHub
git push -u origin main
```

### Step 2: Enable GitHub Pages

1. Go to your repository on GitHub
2. Click **Settings** → **Pages**
3. Under **Source**, select: **GitHub Actions**
4. Save

### Step 3: Wait for Deployment

- Go to **Actions** tab
- Watch the "Deploy Jekyll site to Pages" workflow
- Once complete (✓), your site is live!

**Your site URL:** `https://YOUR_USERNAME.github.io/retirement_planning/`

## Local Testing (Optional)

Test the site locally before deploying:

```bash
# Install dependencies
gem install bundler
bundle install

# Run local server
bundle exec jekyll serve

# View at: http://localhost:4000
```

## Site Features

### Home Page (`index.md`)
- Professional overview
- Feature highlights
- Quick navigation links
- Recent updates section

### Getting Started (`docs/getting-started.md`)
- Installation instructions
- Configuration guide
- Data file setup
- Troubleshooting

### Features (`docs/features.md`)
- Complete feature list
- Portfolio Hub details
- Tax optimization tools
- Analytics capabilities

### User Guides (`docs/guides.md`)
- Step-by-step tutorials
- Common workflows
- Best practices
- Video tutorials (planned)

### API Reference (`docs/api-reference.md`)
- Module documentation
- Function signatures
- Code examples
- Data structures

### Advanced Topics (`docs/advanced/`)
- BETR Roth conversion guide
- Mega Backdoor Roth (to be created)
- Bucket strategy (to be created)
- Monte Carlo analysis (to be created)

## Customization

### Update Site Information

Edit `_config.yml`:

```yaml
title: Your Custom Title
description: Your description
url: "https://YOUR_USERNAME.github.io"
baseurl: "/retirement_planning"
```

### Add Your GitHub Username

Replace `YOUR_USERNAME` in:
- `_config.yml` (url field)
- `index.md` (GitHub links)
- `DEPLOYMENT.md` (example URLs)

### Customize Theme Colors

Create `assets/css/style.scss`:

```scss
---
---

@import "{{ site.theme }}";

.page-header {
  background-color: #155799;
  background-image: linear-gradient(120deg, #155799, #159957);
}
```

## Next Steps

### 1. Complete Additional Guides

Create these files in `docs/guides/`:
- `portfolio-management.md`
- `tax-optimization.md`
- `withdrawal-strategies.md`
- `healthcare-planning.md`
- `social-security.md`

### 2. Add Advanced Topics

Create these files in `docs/advanced/`:
- `mega-backdoor-roth.md`
- `bucket-strategy.md`
- `monte-carlo.md`

### 3. Add Technical Documentation

Create these files in `docs/technical/`:
- `configuration.md`
- `data-formats.md`
- `testing.md`
- `performance.md`
- `modules.md`

### 4. Enhance Content

- Add screenshots
- Create diagrams
- Add code examples
- Include video tutorials

### 5. SEO Optimization

Add to `_config.yml`:

```yaml
plugins:
  - jekyll-seo-tag
  - jekyll-sitemap

google_analytics: UA-XXXXXXXXX-X
```

## Maintenance

### Regular Updates

- Update documentation quarterly
- Review and fix broken links
- Update screenshots
- Add new features

### Monitor Deployment

- Check Actions tab for build status
- Review deployment logs
- Test site after updates

## Troubleshooting

### Build Fails

Check Actions log for errors:
- Invalid YAML syntax
- Missing front matter
- Broken links

### Site Not Updating

- Clear cache (make small change and push)
- Check deployment status in Actions
- Verify Pages settings

### Local Build Issues

```bash
# Clear cache
bundle exec jekyll clean

# Update dependencies
bundle update

# Rebuild
bundle exec jekyll serve
```

## Resources

- **Full Deployment Guide**: See [`DEPLOYMENT.md`](DEPLOYMENT.md)
- **Jekyll Docs**: https://jekyllrb.com/docs/
- **GitHub Pages**: https://docs.github.com/en/pages
- **Architect Theme**: https://github.com/pages-themes/architect

## Support

- **GitHub Issues**: Report bugs or request features
- **Jekyll Talk**: https://talk.jekyllrb.com/
- **GitHub Support**: https://support.github.com/

---

**Ready to deploy?** Follow the 3 steps above and your documentation site will be live in minutes!

**Need help?** Check [`DEPLOYMENT.md`](DEPLOYMENT.md) for detailed instructions.