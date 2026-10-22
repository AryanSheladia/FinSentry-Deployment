# FinSentry dashboard

React + TypeScript + Tailwind CSS, built with Vite. Source follows the planned folders:

- `src/components/`: navigation, payment input, case evidence, human reviews and queue actions.
- `src/pages/`: Overview and Investigate payment. Review queue and case routing are coordinated in `App.tsx`.
- `src/services/`: typed HTTP client and display formatting.
- `src/hooks/`: data loading, status polling, error recovery and result selection.
- `src/sparkovTypes.ts`: public backend contracts.

From this directory, `npm ci` installs locked dependencies and `npm run build` performs TypeScript checks plus production compilation. The built `dist/` is served by FastAPI at `http://127.0.0.1:8000/`; restart the backend after the first build so its asset mount is enabled.

For active UI development, use `npm run dev` at `http://127.0.0.1:5173`. Vite proxies `/api` to the local backend. Stop the dev server with Ctrl+C. An optional public backend address can be configured in `frontend/.env.local` using `VITE_API_BASE_URL`; this file is ignored. Never place Groq keys or database credentials in any `VITE_` variable.

Displayed scores, statuses and evidence come from backend endpoints. Queue counts cover up to the latest 100 submitted cases. Amounts are simulated USD card payments. The automated risk indicator is the calibrated classifier estimate; evidence coverage and the final review action are separate. Case deletion requires confirmation and removes the submitted payment, associated investigations and review notes from the backend database; active investigations cannot be deleted.

The interface uses responsive breakpoints, keyboard-native forms/controls, reduced-motion support and plain-text rendering for explanation/evidence content. Progress polling stops at terminal status and has a bounded wait; saved pending investigations can be reopened.
