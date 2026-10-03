# Publishing checklist

This file is for you, not for reviewers. Delete it once the site is live.

## 1. Create the repository

1. Create a GitHub account at github.com. Your username appears in every link, so choose a professional one (for example `dougcurtis` or `dcurtis-tx`).
2. Click **New repository**. Name it `liquidity-cycle-research`, set it to **Public** (free GitHub Pages requires a public repository), and do not add a README, .gitignore, or license; they are already in this folder.

## 2. Upload the files

The folder contains two hidden items, `.github/` and `.gitignore`. The site will not build without `.github/workflows/weekly-update.yml`.

- **Easiest:** install GitHub Desktop, choose *File → Add local repository* on the unzipped folder, then *Publish repository* to the repo you created.
- **Web upload:** on the empty repo page, click *uploading an existing file* and drag in the folder's contents. On a Mac, press Cmd + Shift + . in Finder first so hidden files show. If `.github` does not upload, use *Add file → Create new file*, type `.github/workflows/weekly-update.yml` as the name, and paste the file's contents.

## 3. Turn on GitHub Pages

*Settings → Pages → Build and deployment → Source:* select **GitHub Actions**.

## 4. Run the first build

*Actions* tab → **Weekly research build** → **Run workflow**. It takes about five to ten minutes. When both jobs show a green check, the site is live at `https://YOUR-USERNAME.github.io/liquidity-cycle-research/`.

If a run fails, open it and read the red step. A Yahoo Finance rate limit is the most likely cause; click **Re-run jobs**. Individual tickers that fail are skipped, and the build continues.

## 5. Replace the placeholder

Edit `README.md` on GitHub (pencil icon) and replace `YOUR-USERNAME` with your username. Saving any file triggers a rebuild.

## 6. Write the Discussion sections

Each file in `research/` ends with a Discussion block hidden inside `<!--` and `-->`, with questions to answer. After reading the live results:

1. Delete the `<!--` line and the `-->` line so the section becomes visible.
2. Replace the AUTHOR prompts with your own interpretation, a few paragraphs per study.
3. Commit. The site rebuilds within minutes.

This is the part reviewers are evaluating, and it is what an interviewer is most likely to ask you about.

## 7. Profile page (optional)

See `extras/profile-README.md`.

## 8. What to submit

Use the live site link in the MSF application's Digital Profile field. The site links to the code through the **Code** item in its navigation.

## Maintenance

- **60-day pause.** GitHub stops scheduled workflows in a public repository after 60 days without a commit. Any edit resets the clock; you can also re-enable the workflow on the Actions tab.
- **FOMC dates.** `reference/fomc_decision_dates.csv` runs through December 2026. Add 2027 dates as the year begins.
- **Changing the universe.** Tickers, baskets, and parameters live in `src/config.py`.
