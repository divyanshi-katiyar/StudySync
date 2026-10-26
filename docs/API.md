# StudySync API reference

Base URL (development): `http://localhost:5000`. Every endpoint lives under `/api`. All bodies are JSON.

## Conventions

- **Success:** `{ "success": true, "data": ... }`. Lists are returned as arrays (paged lists also send `X-Total-Count`); discovery returns `{ items, total, page, pages }`.
- **Error:** `{ "success": false, "message": "...", "errors": { "field": "message" } }` (`errors` only for validation failures).
- **Authentication:** `Authorization: Bearer <accessToken>`. Access tokens last 15 minutes. A refresh token (7 days, rotating) lives in an httpOnly cookie named `studysync_refresh` scoped to `/api/auth`; call `POST /api/auth/refresh` to get a new access token.
- **Identifiers** are opaque strings. **Timestamps** are ISO 8601 UTC with a `Z` suffix.
- **Rate limits:** 300 requests/minute per IP overall, 10/minute for register, login and refresh, 5 failed logins per 15 minutes per IP and email, 10/minute for join-by-code. Exceeding a limit returns 429 with `Retry-After`.

## Status codes

| Code | Meaning |
|---|---|
| 400 | Malformed JSON, or the body is not a JSON object |
| 401 | Missing, invalid or expired token, or wrong credentials |
| 403 | Signed in but not allowed (not a member, or the role is too low) |
| 404 | The resource does not exist |
| 409 | Conflict (duplicate email, already a member, owner cannot leave) |
| 413 | Request body larger than 1 MB |
| 415 | Body is not application/json |
| 422 | Validation failed; `errors` maps each field to a message |
| 429 | Rate limit exceeded; see the Retry-After header |
| 500 | Unexpected server error (details are logged, never returned) |

## Response models

- `user` = `{ id, name, email, role, avatarUrl, createdAt }`
- `group` = `{ id, name, description, subject, color, visibility, ownerId, ownerName, createdAt, memberCount, isMember, myRole, nextSession, inviteCode? }  (inviteCode only for members)`
- `member` = `{ userId, name, role, joinedAt }`
- `resource` = `{ id, groupId, uploadedBy, uploaderName, title, type, url, body, tags[], createdAt, updatedAt, canDelete }`
- `post` = `{ id, groupId, authorId, authorName, title, body, createdAt, updatedAt, commentCount, canEdit, canDelete }`
- `comment` = `{ id, postId, authorId, authorName, body, createdAt, canDelete }`
- `session` = `{ id, groupId, groupName, groupColor, createdBy, createdByName, title, startsAt, durationMin, meetingLink, goingCount, maybeCount, myRsvp, createdAt, updatedAt }`
- `notification` = `{ id, userId, type, message, link, isRead, createdAt }`

## Endpoints

### System

#### `GET /api/health`

Liveness check (also touches the database).

- **Access:** Public
- **Success:** 200 returns `{ status, time }`

### Auth

#### `POST /api/auth/register`

Create an account and sign in. Sets the refresh cookie.

- **Access:** Public
- **Success:** 201 returns `{ user, accessToken, expiresIn }`
- **Errors:** 409, 422, 429

| Body field | Type | Required | Rules |
|---|---|---|---|
| `name` | string | yes | 2 to 60 characters |
| `email` | string | yes | Valid email; stored lower-case; must be unique |
| `password` | string | yes | 8 to 128 characters with a letter and a number |

**Example**

```http
POST /api/auth/register
{
  "name": "Riya Sen",
  "email": "riya@example.com",
  "password": "Password123"
}
-> 201
{
  "success": true,
  "data": {
    "user": {
      "id": "u_ba1f4dc0255a",
      "name": "Riya Sen",
      "email": "riya@example.com",
      "role": "student",
      "avatarUrl": "",
      "createdAt": "2026-10-26T07:06:28.875Z"
    },
    "accessToken": "eyJhbGciOiJIUzI1NiJ9...",
    "expiresIn": 900
  }
}
```

#### `POST /api/auth/login`

Verify credentials and sign in. Wrong email and wrong password give the same 401.

- **Access:** Public
- **Success:** 200 returns `{ user, accessToken, expiresIn }`
- **Errors:** 401, 422, 429

| Body field | Type | Required | Rules |
|---|---|---|---|
| `email` | string | yes | Account email |
| `password` | string | yes | Account password |

**Example**

```http
POST /api/auth/login
{
  "email": "demo@studysync.app",
  "password": "Password123"
}
-> 200
{
  "success": true,
  "data": {
    "user": {
      "id": "u1",
      "name": "Alex Rao",
      "email": "demo@studysync.app",
      "role": "student",
      "avatarUrl": "",
      "createdAt": "2026-08-27T07:06:28.680Z"
    },
    "accessToken": "eyJhbGciOiJIUzI1NiJ9...",
    "expiresIn": 900
  }
}
```

**Example**

```http
POST /api/auth/login   # wrong
{
  "email": "demo@studysync.app",
  "password": "Wrong12345"
}
-> 401
{
  "success": false,
  "message": "The email or password is incorrect."
}
```

#### `POST /api/auth/refresh`

Exchange the httpOnly refresh cookie for a new access token. The refresh token rotates on every use.

- **Access:** Refresh cookie
- **Success:** 200 returns `{ user, accessToken, expiresIn }`
- **Errors:** 401, 403, 429

#### `POST /api/auth/logout`

Revoke the refresh token and clear the cookie. Public on purpose so an expired session can still sign out.

- **Access:** Public
- **Success:** 200 returns `{ ok }`
- **Errors:** 403

### Users

#### `GET /api/users/me`

The current user's profile.

- **Access:** Signed in
- **Success:** 200 returns `user`
- **Errors:** 401

#### `PATCH /api/users/me`

Update name and/or avatar link. Email and role cannot be changed here.

- **Access:** Signed in
- **Success:** 200 returns `user`
- **Errors:** 401, 422

| Body field | Type | Required | Rules |
|---|---|---|---|
| `name` | string | no | 2 to 60 characters |
| `avatarUrl` | string | no | http(s) link or empty |

#### `POST /api/users/me/password`

Change password. Ends all other sessions.

- **Access:** Signed in
- **Success:** 200 returns `{ ok }`
- **Errors:** 401, 422

| Body field | Type | Required | Rules |
|---|---|---|---|
| `currentPassword` | string | yes | Must match the current password |
| `newPassword` | string | yes | Same rules as registration |

#### `GET /api/users/me/dashboard`

Counts, the next 3 sessions and up to 3 of my groups.

- **Access:** Signed in
- **Success:** 200 returns `{ counts, upcomingSessions, myGroups }`
- **Errors:** 401

**Example**

```http
GET /api/users/me/dashboard
-> 200
{
  "success": true,
  "data": {
    "counts": {
      "groups": 3,
      "sessionsThisWeek": 4,
      "newResources": 6
    },
    "upcomingSessions": [
      {
        "id": "s1",
        "groupId": "g1",
        "createdBy": "u2",
        "createdByName": "Priya Nair",
        "title": "Graph problems: practice round",
        "startsAt": "2026-10-27T09:06:28.680Z",
        "durationMin": 90,
        "meetingLink": "https://meet.example.com/graphs",
        "createdAt": "2026-10-22T03:06:28.680Z",
        "updatedAt": null,
        "groupName": "Algorithms Study Circle",
        "groupColor": "#0F7B70",
        "goingCount": 2,
        "maybeCount": 1,
        "myRsvp": null
      },
      {
        "id": "s3",
        "groupId": "g2",
        "createdBy": "u1",
        "createdByName": "Alex Rao",
        "title": "DBMS revision: normalisation",
        "startsAt": "2026-10-28T09:06:28.680Z",
        "durationMin": 75,
        "meetingLink": "https://meet.example.com/dbms",
        "createdAt": "2026-10-22T03:06:28.680Z",
        "updatedAt": null,
        "groupName": "Database Gang",
        "groupColor": "#6446C9",
        "goingCount": 2,
        "maybeCount": 0,
        "myRsvp": null
      },
      {
        "id": "s4",
        "groupId": "g4",
        "createdBy": "u5",
        "createdByName": "Meera Iyer",
        "title": "Build a landing page together",
        "startsAt": "2026-10-29T10:06:28.680Z",
        "durationMin": 120,
        "meetingLink": "https://meet.example.com/webdev",
        "createdAt": "2026-10-22T03:06:28.680Z",
        "updatedAt": null,
        "groupName": "Web Dev Buddies",
        "groupColor": "#1D6FA5",
        "goingCount": 1,
        "maybeCount": 1,
        "myRsvp": null
      }
    ],
    "myGroups": [
      {
        "id"
```

### Groups

#### `GET /api/groups`

Discover public groups (never returns private groups).

- **Access:** Signed in
- **Success:** 200 returns `{ items, total, page, pages }`
- **Errors:** 401, 422

| Query parameter | Type | Notes |
|---|---|---|
| `search` | string | Matches name, subject and description |
| `subject` | string | Exact subject |
| `sort` | string | popular (default) or newest |
| `page` | integer | Default 1 |
| `limit` | integer | Default 6, maximum 50 |

**Example**

```http
GET /api/groups
-> 200
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "g1",
        "name": "Algorithms Study Circle",
        "description": "Weekly problem-solving rounds for interviews and exams. We start with graphs, then move to dynamic programming.",
        "subject": "Data Structures",
        "color": "#0F7B70",
        "visibility": "public",
        "ownerId": "u2",
        "ownerName": "Priya Nair",
        "createdAt": "2026-09-26T07:06:28.680Z",
        "memberCount": 5,
        "isMember": true,
        "myRole": "member",
        "nextSession": {
          "id": "s1",
          "title": "Graph problems: practice round",
          "startsAt": "2026-10-27T09:06:28.680Z"
        },
        "inviteCode": "DAT-4821"
      },
      {
        "id": "g2",
        "name": "Database Gang",
        "description": "Normalisation, indexing and SQL practice for the DBMS paper. Bring your own tricky queries.",
        "subject": "Databases",
        "color": "#6446C9",
        "visibility": "public",
        "ownerId": "u3",
        "ownerName": "Sam Mathew",
        "createdAt": "2026-09-28T07:06:28.680Z",
        "memberCount": 4,
        "isMember": true,
        "myRole": "moderator",
        "nextSession": {
          "id": "s3",
          "title": "DBMS revision: normalisation",
          "startsAt": "2026-10-28T09:06:28.680Z"
        },
        "inviteCode": "DAT-7710"
      }
    ],
    "total": 2,
    "page": 1,
    "pages": 1
  }
}
```

#### `POST /api/groups`

Create a group. The creator becomes owner and receives an invite code.

- **Access:** Signed in
- **Success:** 201 returns `group`
- **Errors:** 401, 422

| Body field | Type | Required | Rules |
|---|---|---|---|
| `name` | string | yes | 3 to 60 characters |
| `description` | string | yes | 10 to 300 characters |
| `subject` | string | yes | One of: Data Structures, Databases, Operating Systems, Web Development, Placements, AI and ML, Compilers, Networks |
| `visibility` | string | yes | public or private |

**Example**

```http
POST /api/groups
{
  "name": "Graph Theory Club",
  "description": "Weekly graph problems and mock interviews.",
  "subject": "Data Structures",
  "visibility": "public"
}
-> 201
{
  "success": true,
  "data": {
    "id": "g_ec37a87456e6",
    "name": "Graph Theory Club",
    "description": "Weekly graph problems and mock interviews.",
    "subject": "Data Structures",
    "color": "#0F7B70",
    "visibility": "public",
    "ownerId": "u1",
    "ownerName": "Alex Rao",
    "createdAt": "2026-10-26T07:06:29.124Z",
    "memberCount": 1,
    "isMember": true,
    "myRole": "owner",
    "nextSession": null,
    "inviteCode": "DAT-K5TEJS"
  }
}
```

#### `GET /api/groups/mine`

Groups I belong to, sorted by name.

- **Access:** Signed in
- **Success:** 200 returns `group[]`
- **Errors:** 401

#### `POST /api/groups/join-by-code`

Join any group (including private) with its invite code. Strictly rate limited.

- **Access:** Signed in
- **Success:** 200 returns `group`
- **Errors:** 401, 404, 409, 422, 429

| Body field | Type | Required | Rules |
|---|---|---|---|
| `code` | string | yes | Invite code, case-insensitive |

#### `GET /api/groups/{group_id}`

Group details. The invite code is included only for members; private groups return 403 to outsiders.

- **Access:** Member (public groups: preview)
- **Success:** 200 returns `group`
- **Errors:** 401, 403, 404

**Example**

```http
GET /api/groups/{group_id}   # private, not a member
-> 403
{
  "success": false,
  "message": "This group is private. Ask the owner for an invite code."
}
```

#### `PATCH /api/groups/{group_id}`

Edit name, description, subject or visibility. Unknown fields are ignored.

- **Access:** Owner
- **Success:** 200 returns `group`
- **Errors:** 401, 403, 404, 422

| Body field | Type | Required | Rules |
|---|---|---|---|
| `name` | string | no | 3 to 60 characters |
| `description` | string | no | 10 to 300 characters |
| `subject` | string | no | One of: Data Structures, Databases, Operating Systems, Web Development, Placements, AI and ML, Compilers, Networks |
| `visibility` | string | no | public or private |

#### `DELETE /api/groups/{group_id}`

Delete the group and everything in it (memberships, resources, posts, comments, sessions).

- **Access:** Owner
- **Success:** 200 returns `{ ok }`
- **Errors:** 401, 403, 404

#### `POST /api/groups/{group_id}/join`

Join a public group.

- **Access:** Signed in
- **Success:** 200 returns `group`
- **Errors:** 401, 403, 404, 409

#### `DELETE /api/groups/{group_id}/leave`

Leave a group. Owners must transfer ownership or delete the group.

- **Access:** Member
- **Success:** 200 returns `{ ok }`
- **Errors:** 401, 403, 404, 409

#### `POST /api/groups/{group_id}/transfer-ownership`

Make another member the owner; the old owner becomes a moderator.

- **Access:** Owner
- **Success:** 200 returns `group`
- **Errors:** 401, 403, 404, 422

| Body field | Type | Required | Rules |
|---|---|---|---|
| `userId` | string | yes | A current member other than yourself |

### Members

#### `GET /api/groups/{group_id}/members`

Members with roles, owner first.

- **Access:** Member
- **Success:** 200 returns `member[]`
- **Errors:** 401, 403, 404

#### `PATCH /api/groups/{group_id}/members/{target_id}`

Set a member's role to moderator or member.

- **Access:** Owner
- **Success:** 200 returns `{ userId, role }`
- **Errors:** 401, 403, 404, 422

| Body field | Type | Required | Rules |
|---|---|---|---|
| `role` | string | yes | moderator or member |

#### `DELETE /api/groups/{group_id}/members/{target_id}`

Remove a member. Moderators can remove only plain members; nobody can remove the owner.

- **Access:** Owner / moderator
- **Success:** 200 returns `{ ok }`
- **Errors:** 401, 403, 404

### Resources

#### `GET /api/groups/{group_id}/resources`

List resources, newest first. Total count is in the X-Total-Count header.

- **Access:** Member
- **Success:** 200 returns `resource[]`
- **Errors:** 401, 403, 404, 422

| Query parameter | Type | Notes |
|---|---|---|
| `type` | string | link, file or note |
| `search` | string | Matches title and tags |
| `tag` | string | Exact tag |
| `page` | integer | Default 1 |
| `limit` | integer | Default and maximum 100 |

#### `POST /api/groups/{group_id}/resources`

Share a resource. Notifies the other members.

- **Access:** Member
- **Success:** 201 returns `resource`
- **Errors:** 401, 403, 404, 422

| Body field | Type | Required | Rules |
|---|---|---|---|
| `title` | string | yes | 3 to 100 characters |
| `type` | string | yes | link, file or note |
| `url` | string | no | Required for link and file; http(s) only, up to 2048 characters |
| `body` | string | no | Required for note; 10 to 5000 characters |
| `tags` | string[] | no | Up to 6 tags; lower-cased, '#' removed, only a-z 0-9 _ - |

**Example**

```http
POST /api/groups/{group_id}/resources
{
  "title": "Dijkstra walkthrough",
  "type": "link",
  "url": "https://example.com/dijkstra",
  "tags": [
    "graphs",
    "Shortest-Path"
  ]
}
-> 201
{
  "success": true,
  "data": {
    "id": "r_db84d72bfabc",
    "groupId": "g1",
    "uploadedBy": "u1",
    "uploaderName": "Alex Rao",
    "title": "Dijkstra walkthrough",
    "type": "link",
    "url": "https://example.com/dijkstra",
    "body": "",
    "tags": [
      "graphs",
      "shortest-path"
    ],
    "createdAt": "2026-10-26T07:06:29.129Z",
    "updatedAt": null,
    "canDelete": true
  }
}
```

**Example**

```http
POST /api/groups/{group_id}/resources   # invalid
{
  "title": "ab",
  "type": "link",
  "url": "javascript:alert(1)"
}
-> 422
{
  "success": false,
  "message": "Please fix the highlighted fields.",
  "errors": {
    "title": "Title needs at least 3 characters.",
    "url": "Enter a full link that starts with http:// or https://."
  }
}
```

#### `PATCH /api/resources/{resource_id}`

Edit title, link or note text, or tags.

- **Access:** Uploader / moderator / owner
- **Success:** 200 returns `resource`
- **Errors:** 401, 403, 404, 422

| Body field | Type | Required | Rules |
|---|---|---|---|
| `title` | string | no | 3 to 100 characters |
| `url` | string | no | Required for link and file; http(s) only, up to 2048 characters |
| `body` | string | no | Required for note; 10 to 5000 characters |
| `tags` | string[] | no | Up to 6 tags; lower-cased, '#' removed, only a-z 0-9 _ - |

#### `DELETE /api/resources/{resource_id}`

Delete a resource and its tags.

- **Access:** Uploader / moderator / owner
- **Success:** 200 returns `{ ok }`
- **Errors:** 401, 403, 404

### Discussion

#### `GET /api/groups/{group_id}/posts`

List discussion posts, newest first, with comment counts. Total in X-Total-Count.

- **Access:** Member
- **Success:** 200 returns `post[]`
- **Errors:** 401, 403, 404

| Query parameter | Type | Notes |
|---|---|---|
| `page` | integer | Default 1 |
| `limit` | integer | Default 50, maximum 100 |

#### `POST /api/groups/{group_id}/posts`

Start a discussion. Notifies the other members.

- **Access:** Member
- **Success:** 201 returns `post`
- **Errors:** 401, 403, 404, 422

| Body field | Type | Required | Rules |
|---|---|---|---|
| `title` | string | yes | 5 to 120 characters |
| `body` | string | yes | 10 to 5000 characters |

#### `GET /api/posts/{post_id}`

A post with its group and comments (oldest first).

- **Access:** Member
- **Success:** 200 returns `post + { group, comments[] }`
- **Errors:** 401, 403, 404

#### `PATCH /api/posts/{post_id}`

Edit title or body.

- **Access:** Author
- **Success:** 200 returns `post`
- **Errors:** 401, 403, 404, 422

| Body field | Type | Required | Rules |
|---|---|---|---|
| `title` | string | no | 5 to 120 characters |
| `body` | string | no | 10 to 5000 characters |

#### `DELETE /api/posts/{post_id}`

Delete a post and its comments.

- **Access:** Author / moderator / owner
- **Success:** 200 returns `{ ok }`
- **Errors:** 401, 403, 404

#### `POST /api/posts/{post_id}/comments`

Reply to a post. Notifies the post's author.

- **Access:** Member
- **Success:** 201 returns `comment`
- **Errors:** 401, 403, 404, 422

| Body field | Type | Required | Rules |
|---|---|---|---|
| `body` | string | yes | 2 to 1000 characters |

#### `DELETE /api/comments/{comment_id}`

Delete a comment.

- **Access:** Author / moderator / owner
- **Success:** 200 returns `{ ok }`
- **Errors:** 401, 403, 404

### Sessions

#### `GET /api/groups/{group_id}/sessions`

All sessions of a group in time order (past and future).

- **Access:** Member
- **Success:** 200 returns `session[]`
- **Errors:** 401, 403, 404

**Example**

```http
GET /api/groups/{group_id}/sessions
-> 200
{
  "success": true,
  "data": [
    {
      "id": "s1",
      "groupId": "g1",
      "createdBy": "u2",
      "createdByName": "Priya Nair",
      "title": "Graph problems: practice round",
      "startsAt": "2026-10-27T09:06:28.680Z",
      "durationMin": 90,
      "meetingLink": "https://meet.example.com/graphs",
      "createdAt": "2026-10-22T03:06:28.680Z",
      "updatedAt": null,
      "groupName": "Algorithms Study Circle",
      "groupColor": "#0F7B70",
      "goingCount": 2,
      "maybeCount": 1,
      "myRsvp": null
    }
  ]
}
```

#### `POST /api/groups/{group_id}/sessions`

Schedule a session. The organiser is marked going; members are notified.

- **Access:** Moderator / owner
- **Success:** 201 returns `session`
- **Errors:** 401, 403, 404, 422

| Body field | Type | Required | Rules |
|---|---|---|---|
| `title` | string | yes | 3 to 100 characters |
| `startsAt` | string | yes | ISO 8601 date-time in the future (a missing offset means UTC) |
| `durationMin` | integer | yes | 15 to 300 (a numeric string such as "60" is accepted) |
| `meetingLink` | string | no | http(s) link or empty |

#### `GET /api/sessions`

Upcoming sessions across all my groups.

- **Access:** Signed in
- **Success:** 200 returns `session[]`
- **Errors:** 401

| Query parameter | Type | Notes |
|---|---|---|
| `limit` | integer | Default 50, maximum 100 |

#### `PATCH /api/sessions/{session_id}`

Edit a session.

- **Access:** Moderator / owner
- **Success:** 200 returns `session`
- **Errors:** 401, 403, 404, 422

| Body field | Type | Required | Rules |
|---|---|---|---|
| `title` | string | no | 3 to 100 characters |
| `startsAt` | string | no | ISO 8601 date-time in the future (a missing offset means UTC) |
| `durationMin` | integer | no | 15 to 300 (a numeric string such as "60" is accepted) |
| `meetingLink` | string | no | http(s) link or empty |

#### `DELETE /api/sessions/{session_id}`

Delete a session and its RSVPs.

- **Access:** Moderator / owner
- **Success:** 200 returns `{ ok }`
- **Errors:** 401, 403, 404

#### `PUT /api/sessions/{session_id}/rsvp`

Set my RSVP (idempotent).

- **Access:** Member
- **Success:** 200 returns `session`
- **Errors:** 401, 403, 404, 422

| Body field | Type | Required | Rules |
|---|---|---|---|
| `status` | string | yes | going, maybe or no |

**Example**

```http
PUT /api/sessions/{session_id}/rsvp
{
  "status": "going"
}
-> 200
{
  "success": true,
  "data": {
    "id": "s1",
    "groupId": "g1",
    "createdBy": "u2",
    "createdByName": "Priya Nair",
    "title": "Graph problems: practice round",
    "startsAt": "2026-10-27T09:06:28.680Z",
    "durationMin": 90,
    "meetingLink": "https://meet.example.com/graphs",
    "createdAt": "2026-10-22T03:06:28.680Z",
    "updatedAt": null,
    "groupName": "Algorithms Study Circle",
    "groupColor": "#0F7B70",
    "goingCount": 3,
    "maybeCount": 1,
    "myRsvp": "going"
  }
}
```

### Notifications

#### `GET /api/notifications`

My notifications, newest first.

- **Access:** Signed in
- **Success:** 200 returns `notification[]`
- **Errors:** 401

| Query parameter | Type | Notes |
|---|---|---|
| `unread` | boolean | true to list only unread |
| `limit` | integer | Default 50, maximum 100 |

**Example**

```http
GET /api/notifications
-> 200
{
  "success": true,
  "data": [
    {
      "id": "n1",
      "userId": "u1",
      "type": "resource",
      "message": "Sam shared a new resource in Database Gang",
      "link": "/app/groups/g2?tab=resources",
      "isRead": false,
      "createdAt": "2026-10-26T01:06:28.680Z"
    },
    {
      "id": "n2",
      "userId": "u1",
      "type": "reply",
      "message": "Priya replied to a post in Algorithms Study Circle",
      "link": "/app/groups/g1/posts/p1",
      "isRead": false,
      "createdAt": "2026-10-25T05:06:28.680Z"
    }
  ]
}
```

#### `PATCH /api/notifications/read-all`

Mark all my notifications as read.

- **Access:** Signed in
- **Success:** 200 returns `{ updated }`
- **Errors:** 401

#### `PATCH /api/notifications/{notification_id}/read`

Mark one notification as read. Other people's notifications return 404.

- **Access:** Signed in
- **Success:** 200 returns `notification`
- **Errors:** 401, 404
