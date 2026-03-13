# GitHub Pages Deployment Guide

This guide explains how to deploy the Financial Planner documentation to GitHub Pages using the Architect theme.

## Prerequisites

- GitHub repository for the project
- GitHub account with Pages enabled
- Git installed locally

## Deployment Steps

### 1. Enable GitHub Pages

1. Go to your repository on GitHub
2. Click **Settings** → **Pages**
3. Under **Source**, select:
   - Source: **GitHub Actions**
4. Save the settings

### 2. Push to GitHub

If you haven't already pushed your code:

```bash
# Initialize git repository (if not already done)
git init

# Add all files
git add .

# Commit changes
git commit -m "Add GitHub Pages documentation site"

# Add remote repository
git remote add origin https://github.com/yourusername/retirement_planning.git

# Push to GitHub
git push -u origin main
```

### 3. Automatic Deployment

The GitHub Actions workflow (`.github/workflows/jekyll.yml`) will automatically:
1. Build the Jekyll site
2. Deploy to GitHub Pages
3. Make it available at: `https://yourusername.github.io/retirement_planning/`

### 4. Monitor Deployment

1. Go to **Actions** tab in your repository
2. Watch the "Deploy Jekyll site to Pages" workflow
3. Once complete (green checkmark), your site is live!

## Local Testing

To test the site locally before deploying:

### Install Dependencies

```bash
# Install Ruby (if not already installed)
# On macOS:
brew install ruby

# On Ubuntu/Debian:
sudo apt-get install ruby-full

# Install Bundler
gem install bundler

# Install Jekyll and dependencies
bundle install
```

### Run Local Server

```bash
# Start Jekyll server
bundle exec jekyll serve

# Or with live reload
bundle exec jekyll serve --livereload

# Site will be available at: http://localhost:4000
```

### Build Site Locally

```bash
# Build the site (output to _site directory)
bundle exec jekyll build

# Build with production environment
JEKYLL_ENV=production bundle exec jekyll build
```

## Site Structure

```
retirement_planning/
├── _config.yml              # Jekyll configuration
├── Gemfile                  # Ruby dependencies
├── index.md                 # Home page
├── docs/                    # Documentation pages
│   ├── getting-started.md
│   ├── features.md
│   ├── guides.md
│   ├── api-reference.md
│   ├── guides/              # User guides
│   ├── advanced/            # Advanced topics
│   │   └── betr-guide.md
│   └── technical/           # Technical docs
├── .github/
│   └── workflows/
│       └── jekyll.yml       # GitHub Actions workflow
└── README.md                # Project README
```

## Customization

### Update Site Title and Description

Edit `_config.yml`:

```yaml
title: Your Custom Title
description: Your custom description
url: "https://yourusername.github.io"
baseurl: "/retirement_planning"
```

### Change Theme Colors

The Architect theme uses default colors. To customize:

1. Create `assets/css/style.scss`:

```scss
---
---

@import "{{ site.theme }}";

// Custom styles here
.page-header {
  background-color: #155799;
  background-image: linear-gradient(120deg, #155799, #159957);
}
```

### Add Custom Navigation

Edit `_config.yml` to modify navigation:

```yaml
navigation:
  - title: Home
    url: /
  - title: Getting Started
    url: /docs/getting-started
  - title: Features
    url: /docs/features
```

### Add Google Analytics

Add to `_config.yml`:

```yaml
google_analytics: UA-XXXXXXXXX-X
```

## Updating Documentation

### Add New Page

1. Create new `.md` file in appropriate directory
2. Add front matter:

```yaml
---
layout: default
title: Page Title
---
```

3. Write content in Markdown
4. Commit and push to GitHub

### Update Existing Page

1. Edit the `.md` file
2. Commit and push changes
3. GitHub Actions will automatically rebuild and deploy

## Troubleshooting

### Build Fails

**Check the Actions log:**
1. Go to **Actions** tab
2. Click on failed workflow
3. Review error messages

**Common issues:**
- Invalid YAML in `_config.yml`
- Missing front matter in `.md` files
- Broken internal links

### Site Not Updating

**Clear GitHub Pages cache:**
1. Make a small change to any file
2. Commit and push
3. Wait 1-2 minutes for rebuild

**Check deployment status:**
- Actions tab should show successful deployment
- Pages settings should show "Your site is live at..."

### Local Build Issues

**Bundle install fails:**
```bash
# Update RubyGems
gem update --system

# Install bundler
gem install bundler

# Try again
bundle install
```

**Jekyll serve fails:**
```bash
# Clear cache
bundle exec jekyll clean

# Rebuild
bundle exec jekyll serve
```

## Custom Domain (Optional)

To use a custom domain:

1. Add `CNAME` file to repository root:
```
docs.yoursite.com
```

2. Configure DNS:
   - Add CNAME record pointing to: `yourusername.github.io`
   - Or A records pointing to GitHub Pages IPs

3. Update `_config.yml`:
```yaml
url: "https://docs.yoursite.com"
baseurl: ""
```

## Performance Optimization

### Enable Caching

GitHub Pages automatically caches static assets.

### Optimize Images

- Use compressed images
- Consider WebP format
- Add to `.gitignore` if very large

### Minimize Build Time

Exclude unnecessary files in `_config.yml`:

```yaml
exclude:
  - .venv/
  - .pytest_cache/
  - "*.py"
  - "*.pyc"
  - requirements.txt
```

## Security

### Protect Sensitive Data

Ensure these are in `.gitignore`:
- `.env` files
- API keys
- Personal financial data
- `portfolio_data_truth.csv`
- `retirement_config.json`

### Review Public Content

Before deploying:
- Remove any personal information
- Check for hardcoded credentials
- Verify no sensitive data in examples

## Maintenance

### Regular Updates

- Update Jekyll and gems: `bundle update`
- Review and update documentation quarterly
- Check for broken links
- Update screenshots and examples

### Monitoring

- Check GitHub Actions for build failures
- Monitor site analytics (if enabled)
- Review user feedback and issues

## Additional Resources

- [GitHub Pages Documentation](https://docs.github.com/en/pages)
- [Jekyll Documentation](https://jekyllrb.com/docs/)
- [Architect Theme](https://github.com/pages-themes/architect)
- [Markdown Guide](https://www.markdownguide.org/)

## Support

For issues with:
- **GitHub Pages**: [GitHub Support](https://support.github.com/)
- **Jekyll**: [Jekyll Talk](https://talk.jekyllrb.com/)
- **This Project**: [GitHub Issues](https://github.com/yourusername/retirement_planning/issues)

---

**Last Updated**: March 2026