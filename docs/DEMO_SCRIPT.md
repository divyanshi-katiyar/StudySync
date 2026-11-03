# Demo video script (about 4 minutes)

The task asks for a short screen recording of the working application. Record it yourself with any screen recorder
(Windows: Win+G Game Bar or OBS Studio; macOS: Shift+Cmd+5; Linux: OBS or SimpleScreenRecorder). Save it as MP4 and keep it under about 50 MB.

## Before recording
1. Start the API with fresh demo data: `cd server && python manage.py reset && python run.py`
2. Start the front end: `cd client && npm run dev` (with `VITE_API_URL=http://localhost:5000/api` in `client/.env`)
3. Open two browser windows side by side: one normal, one private/incognito (they must not share cookies). Zoom to 110% so text is readable.
4. Optional: open the Network tab in the left window to show the `stream` request staying open.

## Shot list
| Time | Say | Do |
|---|---|---|
| 0:00 | "This is StudySync, a full-stack study-group app: React front end, Flask API, SQLite database." | Show the two terminals running, then the landing page |
| 0:20 | "Registration validates input on the client and the server." | Register with a bad email (inline error), then a valid one; you land on the dashboard |
| 0:50 | "Everything on screen comes from the database through the REST API." | Show dashboard counts, My groups, Discover search for "data", filters and paging in the URL |
| 1:25 | "Roles and privacy are enforced on the server." | Left window: sign in as demo@studysync.app / Password123. Try the private Compiler Design group (clear error). Join it with code COM-2026 |
| 2:00 | "Now the real-time part: two users, two browsers." | Right (private) window: sign in as priya@studysync.app / Password123 and open Algorithms Study Circle. Left window: open the same group, Resources tab |
| 2:15 | "When Priya shares a resource, Alex sees it without refreshing." | Right: Add resource. Left: toast appears, bell count goes up, the list updates by itself |
| 2:50 | "Discussions and RSVPs update live too." | Right: start a discussion. Left: Discussion tab updates. Left: RSVP Going on a session; right window's Sessions tab count changes |
| 3:20 | "Errors are handled gracefully." | Stop the API (Ctrl+C): the "Live updates are paused" banner appears; try an action to show the readable error; restart the API and show it reconnect |
| 3:45 | "Tests: 127 server tests and 22 client integration tests, all passing." | In a terminal run `python scripts/e2e.py` |
| 4:00 | "Code, README and documentation are in the repository." | Show the repository folder and README |

## Tips
- Rehearse once. The live-update steps are the highlight, so pause a second after each action so viewers see the change.
- If you deploy (Vercel and Render), add the live URL to the README and show it instead of localhost.
