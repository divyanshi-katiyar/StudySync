# StudySync front end (Week 2)

StudySync is a collaborative study-group platform: students create or join groups, share resources, hold
discussions and schedule sessions. This repository contains the **React front end** built for Week 2 of the
Full Stack Developer internship. It follows the architecture, wireframes and API design from the Week 1 report.

The Express and MongoDB back end is built in Week 3. Until then the app runs against a **mock API** that stores
data in the browser (`localStorage`), so every screen works end to end without a server.

## Try it

```
npm install
npm run dev        # http://localhost:5173
```

Log in with the demo account (or press "Try the demo account" on the landing page):

| Email | Password |
| --- | --- |
| `demo@studysync.app` | `Password123` |

You can also register a new account. A private demo group is joined with the invite code `COM-2026`.

Other scripts:

| Command | What it does |
| --- | --- |
| `npm run build` | Production build into `dist/` |
| `npm run preview` | Serves the production build locally |
| `npm test` | Runs the unit and interaction tests once (Vitest + Testing Library) |
| `npm run test:watch` | Re-runs tests on file changes |

Requirements: Node.js 18 or newer.

## Pages and navigation

| Route | View | Access |
| --- | --- | --- |
| `/` | Landing page | Public |
| `/login`, `/register` | Authentication | Public |
| `/app/dashboard` | Dashboard: counts, upcoming sessions with RSVP, your groups, recent activity | Signed in |
| `/app/groups` | My groups, create a group, join with invite code | Signed in |
| `/app/discover` | Search and filter public groups, join from the card | Signed in |
| `/app/groups/:id` | **Detail view**: group workspace with Resources, Discussion, Sessions and Members tabs | Member (public groups show a preview) |
| `/app/groups/:id/posts/:postId` | Discussion thread with replies | Member |
| `/app/sessions` | All upcoming sessions across groups | Signed in |
| `/app/profile` | Edit name, reset demo data | Signed in |
| `*` | "Page not found" | Public |

Signed-out visitors who open an `/app/...` link are sent to the login page and returned to that link afterwards.
Notification links, the global search box and the tab state all use real URLs, so Back, Forward, bookmarks and
shared links work.

## Features (mapped to the Week 1 requirements)

- **FR-01/02 Authentication:** register and log in with inline validation, generic error for wrong credentials, session restored on reload, log out.
- **FR-03 Profile:** edit your name.
- **FR-04 Create group:** name, subject, description, public or private; the owner gets an invite code.
- **FR-05 Discover:** debounced search, subject filter, sorting, pagination, filters kept in the URL.
- **FR-06 Join and leave:** join public groups, join any group with an invite code, leave with confirmation.
- **FR-07 Roles:** owner, moderator, member. Owners change roles and remove members, moderators remove members and schedule sessions, the uploader or staff can delete resources.
- **FR-08 Resources:** add links, file links or notes with tags; search, filter by type, delete with confirmation.
- **FR-09 Discussion:** start posts, open a thread, reply.
- **FR-10 Sessions:** schedule (staff only), RSVP with Going, Maybe or Can't go (optimistic update).
- **FR-11 Notifications:** bell with unread count, mark one or all as read. One simulated live event arrives about 25 seconds after sign-in to show how Socket.io updates will look.
- **FR-12 Dashboard:** summary counts, next sessions, groups, recent activity.

## How I built it (development process)

1. **Setup:** Vite + React 18, Tailwind CSS 3 for styling, React Router 6 for navigation, Vitest and Testing Library for tests.
2. **Design tokens first:** colours, typefaces and focus styles are defined once in `tailwind.config.js` and `src/index.css`.
3. **Data layer before screens:** `src/api/mockDb.js` seeds eight collections that mirror the Week 1 ER diagram, and `src/api/index.js` exposes one function per planned REST endpoint, with simulated latency and real error cases (401, 403, 404, 409, 422). Building this first meant every screen could be written against realistic loading, empty and error states.
4. **Reusable UI kit:** buttons, form fields, modal, tabs, toasts, skeletons and empty/error states in `src/components/ui`, each written once with accessibility built in.
5. **Layouts and routing:** public layout and an app shell with sidebar (desktop) and bottom navigation (mobile), plus route guards.
6. **Features page by page:** authentication, groups, resources, discussion, sessions, notifications, dashboard.
7. **Testing by simulating users:** `src/test` drives the real app with user-event: typing, clicking, keyboard navigation, dialogs (see "Testing").
8. **Wireframe changes:** the Week 1 sidebar listed Resources and Settings. Resources live inside each group, so the sidebar now has Sessions and Profile instead.

## Project structure

```
src/
  api/            mockDb.js (seed + localStorage), index.js (endpoint-shaped functions)
  components/
    ui/           Button, Fields, Modal, ConfirmDialog, Tabs, Avatar, Badge, Skeleton, States, PageHeader, Logo
    layout/       PublicLayout, AppLayout, ProtectedRoute, NotificationBell
    groups/       GroupCard, SessionItem, ResourcesTab, DiscussionTab, SessionsTab, MembersTab, create/join modals
  context/        AuthContext, ToastContext, NotificationsContext
  hooks/          useAsync, useForm, useDebounce, usePageTitle, useRsvp
  pages/          Landing, AuthPage, Dashboard, MyGroups, Discover, GroupDetail, PostDetail, SessionsPage, Profile, NotFound
  utils/          format.js, validation.js, subjects.js
  test/           helpers and test suites
```

## Patterns and libraries

| Choice | Why |
| --- | --- |
| **React 18 function components and hooks** | Small composable pieces; no class components. |
| **Container/presentational split** | Pages and tab components fetch data; `GroupCard`, `SessionItem` and the UI kit only render props. |
| **Context for cross-cutting state** | Auth, toasts and notifications are needed everywhere; page data stays local to the page. |
| **Custom hooks** | `useAsync` (loading/error/data with optimistic `setData`), `useForm` (values, errors, `bind`), `useRsvp`, `useDebounce`. |
| **API layer behind one module** | Components never touch `localStorage`. In Week 3 only `src/api/index.js` changes (functions become Axios calls). |
| **URL as state** | Search filters, pagination and the active tab are in the query string. |
| **Optimistic updates** | RSVP updates instantly and rolls back with an error toast if the request fails. |
| **React Router 6** | Nested routes, layout routes, route guard, `NavLink` active state. |
| **Tailwind CSS 3** | Utility classes with a small token set, mobile-first breakpoints. |
| **lucide-react** | Icons, all marked `aria-hidden` and paired with text. |
| **@fontsource-variable** | Self-hosted Bricolage Grotesque (headings) and Public Sans (body), no external font requests. |
| **Vitest + Testing Library + user-event** | Tests describe what a user does and sees. |

## Design system

The look is built around a study desk: **graph paper** behind the landing hero, notebook **spines** in a subject colour on group cards, **index tabs** for the group sections, a **ticket stub** date block for sessions, and a **highlighter** yellow used only to mark what is active, new or selected (unread notifications, the current navigation item, the chosen RSVP).

| Token | Value | Use |
| --- | --- | --- |
| ink | `#14213D` | Text, dark surfaces |
| paper | `#F4F6FA` | Page background |
| marker | `#2F4FCF` | Primary actions, links, focus ring |
| hilite | `#FFE45C` | Highlighter: active, new, selected |
| muted | `#4F5A73` | Secondary text |
| line | `#D7DCE6` | Borders |

Typefaces: Bricolage Grotesque for headings, Public Sans for body text.

## Responsiveness

Mobile-first. Below 768 px the sidebar becomes a bottom navigation bar and dialogs slide up as bottom sheets; the
group, session and form layouts stack; tab lists scroll horizontally. From 768 px the sidebar appears, and card
grids grow to two and three columns. Inputs use 16 px text on phones so iOS does not zoom, and touch targets are at
least 44 px high.

## Accessibility

- Skip link, landmarks (`header`, `nav`, `main`, `aside`), one `h1` per view, and a page title per route.
- After each navigation, focus moves to the main region so keyboard and screen-reader users start at the new content.
- Every input has a visible label; errors are linked with `aria-describedby`, flagged with `aria-invalid`, and focus moves to the first invalid field after a failed submit.
- Modals are labelled dialogs that trap focus, close with Escape, lock page scroll and return focus to the opener.
- Tabs follow the WAI-ARIA pattern (arrow keys, Home, End, roving tabindex).
- Toasts use a polite live region; the result count on Discover is announced as filters change.
- Visible focus ring on every control; colour is never the only cue (subject names, role badges and "Unread" text accompany colours).
- Links that open a new tab say so for screen readers; `prefers-reduced-motion` is respected.

## Testing

`npm test` runs 23 tests (unit tests for validation and formatting, plus interaction tests that drive the whole app):

- sign-up and login flows, validation messages and focus, wrong credentials, duplicate email, route protection;
- searching and filtering groups, empty state, joining from a card, joining a private group with a code;
- tab keyboard navigation, adding a resource through the dialog, Escape and focus return, RSVP, replying to a thread, private-group access, role-based buttons.

## Mock API and the Week 3 hand-over

Each function in `src/api/index.js` is annotated with the endpoint it stands in for (for example
`POST /api/groups/:id/join`). Passwords are stored in plain text in the browser **for the demo only**; the real
API will hash them with bcrypt and issue JWT access and refresh tokens. `.env.example` already names the
`VITE_API_URL` that will point at the Express server.

## Known limitations

- Data lives in the browser: it is per device and can be cleared with Profile, then Reset demo data.
- File resources are share links; direct file upload (Cloudinary) comes with the back end.
- Real-time updates are simulated once per sign-in; Socket.io arrives in Week 4.
- No email reminders or admin panel (marked Could in the Week 1 requirements).
