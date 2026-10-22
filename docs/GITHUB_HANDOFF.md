# Sequential GitHub handoff

Target: https://github.com/AryanSheladia/FinSentry-AI, branch `main`.

The current remote tree was empty at commit `500c37381f40fc1e3109587cc01f489d87f63acb`. Existing Git history is retained. Each package adds distinct paths; upload in this order:

| Order | Package | Assigned responsibility |
|---|---|---|
| 1 | Parth | Model/data code, reproducibility, dependencies and source setup |
| 2 | Aryan | Validated input, history retrieval, API, persistence, deletion and backend startup |
| 3 | Yash | Agent coordination, behavioral/intelligence evidence, decisions and explanation/demo walkthroughs |
| 4 | Pratik | Analyst frontend, monitoring, interface tests and final integration |

These are balanced responsibility scopes, not a claim of equal measured effort or separate original authorship. The implementation was prepared with Codex assistance on Aryan's device. Each member should understand, review, test and document their assigned scope before committing it. Record concrete observations and fixes in their own `docs/reviews/<Name>.md`; unfilled templates are not evidence of completed reviews. Do not fabricate identities, signatures, review results, authorship, dates or co-author trailers.

## Access and identity

Aryan must invite the other three GitHub accounts as collaborators with push access; each person must accept the invitation. No invitations were sent automatically. Each member uses their own GitHub authentication and a commit email attached to their own account. No one should share an API key, password or access token.

The package wrapper contains `APPLY_PACKAGE.py`, `PACKAGE_MANIFEST.json`, `START_HERE.md`, and `project/`. Only the **contents of `project/`** belong in the repository root. Do not upload the ZIP, member-name folder, wrapper files or an extra `project/` directory into GitHub.

## For each member

1. Wait for the previous person to push. Clone the repository into a new folder outside the extracted package, or use an existing clean clone. Check out `main` and run `git pull --ff-only origin main` before applying your package.
2. Confirm your local Git identity. Set `git config user.name "Your actual name"` and `git config user.email "YOUR_GITHUB_LINKED_EMAIL"` for your own clone if needed. Use your actual linked email or GitHub-provided noreply email. Do not use another member's identity.
3. Read your package instructions and source files. Run the supplied helper against the clone: `python PATH_TO_PACKAGE\APPLY_PACKAGE.py --repo PATH_TO_CLONE --stage`. It verifies the target repository, clean working tree, earlier-package receipts, manifest hashes and overwrite safety; it copies/stages only the listed files. It does not commit or push.
4. Complete your own review note, run the applicable checks, and write any real fixes. Stage your note/fixes explicitly. A command that was not run or failed must be recorded honestly.
5. Inspect `git diff --cached --stat` and `git diff --cached`. Commit with the supplied integration message, then `git push origin main`. Tell the next member that your push is complete. Each commit is a real handoff/integration of assisted source; it is not evidence that its committer independently wrote every line.
6. If push is rejected, stop and run `git pull --rebase origin main`, inspect conflicts, and retry after resolving them. Never force-push. If branch protection requires a pull request, create a feature branch, push it and merge its PR into `main` before the next handoff.

Do not edit another package's files just to equalize counts. Record needed cross-scope fixes normally, after coordinating with the relevant member. Packages 1–3 are partial source snapshots; the complete application is assembled after package 4. Follow `docs/DATA_AND_MODEL_SETUP.md` to recreate local-only data/model/database assets.

## What GitHub credit means

Uploading four ZIPs or producing similar file/line counts does not establish 25% contribution each or guarantee academic marks. GitHub associates commits using their author email; profile contribution eligibility generally requires the default branch (or merging into it), and updates can take up to 24 hours. Follow [GitHub's contribution troubleshooting documentation](https://docs.github.com/en/account-and-profile/how-tos/contribution-settings/troubleshooting-missing-contributions). The useful record is the actual commits, reviews, tests and fixes each person performs.

The preparation process does not push source, create commits, rewrite history or attribute work to teammates. The packaging helper only records the intended handoff scope and file hashes. Blank review templates remain blank until the named reviewer fills them.
