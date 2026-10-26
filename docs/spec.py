"""Single source of truth for the API documentation. scripts/gen_docs.py turns this into docs/API.md and docs/openapi.yaml,
and tests/test_docs.py fails if a route exists in the code but not here (or the other way round)."""

# field = (name, type, required, description)
def F(name, type_, required, desc):
    return {"name": name, "type": type_, "required": required, "description": desc}


GROUP_FIELDS = [
    F("name", "string", True, "3 to 60 characters"),
    F("description", "string", True, "10 to 300 characters"),
    F("subject", "string", True, "One of: Data Structures, Databases, Operating Systems, Web Development, Placements, AI and ML, Compilers, Networks"),
    F("visibility", "string", True, "public or private"),
]
RESOURCE_FIELDS = [
    F("title", "string", True, "3 to 100 characters"),
    F("type", "string", True, "link, file or note"),
    F("url", "string", False, "Required for link and file; http(s) only, up to 2048 characters"),
    F("body", "string", False, "Required for note; 10 to 5000 characters"),
    F("tags", "string[]", False, "Up to 6 tags; lower-cased, '#' removed, only a-z 0-9 _ -"),
]
SESSION_FIELDS = [
    F("title", "string", True, "3 to 100 characters"),
    F("startsAt", "string", True, "ISO 8601 date-time in the future (a missing offset means UTC)"),
    F("durationMin", "integer", True, "15 to 300 (a numeric string such as \"60\" is accepted)"),
    F("meetingLink", "string", False, "http(s) link or empty"),
]
PAGING = [("page", "integer", "Page number, default 1"), ("limit", "integer", "Items per page, default and maximum shown per endpoint")]

# (method, path, tag, access, summary, body fields, query params, success status, returns, extra error statuses)
ENDPOINTS = [
    ("GET", "/api/health", "System", "Public", "Liveness check (also touches the database).", [], [], 200, "{ status, time }", []),
    ("POST", "/api/auth/register", "Auth", "Public", "Create an account and sign in. Sets the refresh cookie.",
     [F("name", "string", True, "2 to 60 characters"), F("email", "string", True, "Valid email; stored lower-case; must be unique"), F("password", "string", True, "8 to 128 characters with a letter and a number")],
     [], 201, "{ user, accessToken, expiresIn }", [409, 422, 429]),
    ("POST", "/api/auth/login", "Auth", "Public", "Verify credentials and sign in. Wrong email and wrong password give the same 401.",
     [F("email", "string", True, "Account email"), F("password", "string", True, "Account password")], [], 200, "{ user, accessToken, expiresIn }", [401, 422, 429]),
    ("POST", "/api/auth/refresh", "Auth", "Refresh cookie", "Exchange the httpOnly refresh cookie for a new access token. The refresh token rotates on every use.", [], [], 200, "{ user, accessToken, expiresIn }", [401, 403, 429]),
    ("POST", "/api/auth/logout", "Auth", "Public", "Revoke the refresh token and clear the cookie. Public on purpose so an expired session can still sign out.", [], [], 200, "{ ok }", [403]),
    ("GET", "/api/users/me", "Users", "Signed in", "The current user's profile.", [], [], 200, "user", []),
    ("PATCH", "/api/users/me", "Users", "Signed in", "Update name and/or avatar link. Email and role cannot be changed here.",
     [F("name", "string", False, "2 to 60 characters"), F("avatarUrl", "string", False, "http(s) link or empty")], [], 200, "user", [422]),
    ("POST", "/api/users/me/password", "Users", "Signed in", "Change password. Ends all other sessions.",
     [F("currentPassword", "string", True, "Must match the current password"), F("newPassword", "string", True, "Same rules as registration")], [], 200, "{ ok }", [422]),
    ("GET", "/api/users/me/dashboard", "Users", "Signed in", "Counts, the next 3 sessions and up to 3 of my groups.", [], [], 200, "{ counts, upcomingSessions, myGroups }", []),
    ("GET", "/api/groups", "Groups", "Signed in", "Discover public groups (never returns private groups).", [],
     [("search", "string", "Matches name, subject and description"), ("subject", "string", "Exact subject"), ("sort", "string", "popular (default) or newest"), ("page", "integer", "Default 1"), ("limit", "integer", "Default 6, maximum 50")],
     200, "{ items, total, page, pages }", [422]),
    ("POST", "/api/groups", "Groups", "Signed in", "Create a group. The creator becomes owner and receives an invite code.", GROUP_FIELDS, [], 201, "group", [422]),
    ("GET", "/api/groups/mine", "Groups", "Signed in", "Groups I belong to, sorted by name.", [], [], 200, "group[]", []),
    ("POST", "/api/groups/join-by-code", "Groups", "Signed in", "Join any group (including private) with its invite code. Strictly rate limited.", [F("code", "string", True, "Invite code, case-insensitive")], [], 200, "group", [404, 409, 422, 429]),
    ("GET", "/api/groups/{group_id}", "Groups", "Member (public groups: preview)", "Group details. The invite code is included only for members; private groups return 403 to outsiders.", [], [], 200, "group", [403, 404]),
    ("PATCH", "/api/groups/{group_id}", "Groups", "Owner", "Edit name, description, subject or visibility. Unknown fields are ignored.", [F(f["name"], f["type"], False, f["description"]) for f in GROUP_FIELDS], [], 200, "group", [403, 404, 422]),
    ("DELETE", "/api/groups/{group_id}", "Groups", "Owner", "Delete the group and everything in it (memberships, resources, posts, comments, sessions).", [], [], 200, "{ ok }", [403, 404]),
    ("POST", "/api/groups/{group_id}/join", "Groups", "Signed in", "Join a public group.", [], [], 200, "group", [403, 404, 409]),
    ("DELETE", "/api/groups/{group_id}/leave", "Groups", "Member", "Leave a group. Owners must transfer ownership or delete the group.", [], [], 200, "{ ok }", [403, 404, 409]),
    ("POST", "/api/groups/{group_id}/transfer-ownership", "Groups", "Owner", "Make another member the owner; the old owner becomes a moderator.", [F("userId", "string", True, "A current member other than yourself")], [], 200, "group", [403, 404, 422]),
    ("GET", "/api/groups/{group_id}/members", "Members", "Member", "Members with roles, owner first.", [], [], 200, "member[]", [403, 404]),
    ("PATCH", "/api/groups/{group_id}/members/{target_id}", "Members", "Owner", "Set a member's role to moderator or member.", [F("role", "string", True, "moderator or member")], [], 200, "{ userId, role }", [403, 404, 422]),
    ("DELETE", "/api/groups/{group_id}/members/{target_id}", "Members", "Owner / moderator", "Remove a member. Moderators can remove only plain members; nobody can remove the owner.", [], [], 200, "{ ok }", [403, 404]),
    ("GET", "/api/groups/{group_id}/resources", "Resources", "Member", "List resources, newest first. Total count is in the X-Total-Count header.", [],
     [("type", "string", "link, file or note"), ("search", "string", "Matches title and tags"), ("tag", "string", "Exact tag"), ("page", "integer", "Default 1"), ("limit", "integer", "Default and maximum 100")], 200, "resource[]", [403, 404, 422]),
    ("POST", "/api/groups/{group_id}/resources", "Resources", "Member", "Share a resource. Notifies the other members.", RESOURCE_FIELDS, [], 201, "resource", [403, 404, 422]),
    ("PATCH", "/api/resources/{resource_id}", "Resources", "Uploader / moderator / owner", "Edit title, link or note text, or tags.", [F(f["name"], f["type"], False, f["description"]) for f in RESOURCE_FIELDS if f["name"] != "type"], [], 200, "resource", [403, 404, 422]),
    ("DELETE", "/api/resources/{resource_id}", "Resources", "Uploader / moderator / owner", "Delete a resource and its tags.", [], [], 200, "{ ok }", [403, 404]),
    ("GET", "/api/groups/{group_id}/posts", "Discussion", "Member", "List discussion posts, newest first, with comment counts. Total in X-Total-Count.", [], [("page", "integer", "Default 1"), ("limit", "integer", "Default 50, maximum 100")], 200, "post[]", [403, 404]),
    ("POST", "/api/groups/{group_id}/posts", "Discussion", "Member", "Start a discussion. Notifies the other members.", [F("title", "string", True, "5 to 120 characters"), F("body", "string", True, "10 to 5000 characters")], [], 201, "post", [403, 404, 422]),
    ("GET", "/api/posts/{post_id}", "Discussion", "Member", "A post with its group and comments (oldest first).", [], [], 200, "post + { group, comments[] }", [403, 404]),
    ("PATCH", "/api/posts/{post_id}", "Discussion", "Author", "Edit title or body.", [F("title", "string", False, "5 to 120 characters"), F("body", "string", False, "10 to 5000 characters")], [], 200, "post", [403, 404, 422]),
    ("DELETE", "/api/posts/{post_id}", "Discussion", "Author / moderator / owner", "Delete a post and its comments.", [], [], 200, "{ ok }", [403, 404]),
    ("POST", "/api/posts/{post_id}/comments", "Discussion", "Member", "Reply to a post. Notifies the post's author.", [F("body", "string", True, "2 to 1000 characters")], [], 201, "comment", [403, 404, 422]),
    ("DELETE", "/api/comments/{comment_id}", "Discussion", "Author / moderator / owner", "Delete a comment.", [], [], 200, "{ ok }", [403, 404]),
    ("GET", "/api/groups/{group_id}/sessions", "Sessions", "Member", "All sessions of a group in time order (past and future).", [], [], 200, "session[]", [403, 404]),
    ("POST", "/api/groups/{group_id}/sessions", "Sessions", "Moderator / owner", "Schedule a session. The organiser is marked going; members are notified.", SESSION_FIELDS, [], 201, "session", [403, 404, 422]),
    ("GET", "/api/sessions", "Sessions", "Signed in", "Upcoming sessions across all my groups.", [], [("limit", "integer", "Default 50, maximum 100")], 200, "session[]", []),
    ("PATCH", "/api/sessions/{session_id}", "Sessions", "Moderator / owner", "Edit a session.", [F(f["name"], f["type"], False, f["description"]) for f in SESSION_FIELDS], [], 200, "session", [403, 404, 422]),
    ("DELETE", "/api/sessions/{session_id}", "Sessions", "Moderator / owner", "Delete a session and its RSVPs.", [], [], 200, "{ ok }", [403, 404]),
    ("PUT", "/api/sessions/{session_id}/rsvp", "Sessions", "Member", "Set my RSVP (idempotent).", [F("status", "string", True, "going, maybe or no")], [], 200, "session", [403, 404, 422]),
    ("GET", "/api/notifications", "Notifications", "Signed in", "My notifications, newest first.", [], [("unread", "boolean", "true to list only unread"), ("limit", "integer", "Default 50, maximum 100")], 200, "notification[]", []),
    ("PATCH", "/api/notifications/read-all", "Notifications", "Signed in", "Mark all my notifications as read.", [], [], 200, "{ updated }", []),
    ("PATCH", "/api/notifications/{notification_id}/read", "Notifications", "Signed in", "Mark one notification as read. Other people's notifications return 404.", [], [], 200, "notification", [404]),
]

ERROR_TEXT = {
    400: "Malformed JSON, or the body is not a JSON object",
    401: "Missing, invalid or expired token, or wrong credentials",
    403: "Signed in but not allowed (not a member, or the role is too low)",
    404: "The resource does not exist",
    409: "Conflict (duplicate email, already a member, owner cannot leave)",
    413: "Request body larger than 1 MB",
    415: "Body is not application/json",
    422: "Validation failed; `errors` maps each field to a message",
    429: "Rate limit exceeded; see the Retry-After header",
    500: "Unexpected server error (details are logged, never returned)",
}

MODELS = {
    "user": "{ id, name, email, role, avatarUrl, createdAt }",
    "group": "{ id, name, description, subject, color, visibility, ownerId, ownerName, createdAt, memberCount, isMember, myRole, nextSession, inviteCode? }  (inviteCode only for members)",
    "member": "{ userId, name, role, joinedAt }",
    "resource": "{ id, groupId, uploadedBy, uploaderName, title, type, url, body, tags[], createdAt, updatedAt, canDelete }",
    "post": "{ id, groupId, authorId, authorName, title, body, createdAt, updatedAt, commentCount, canEdit, canDelete }",
    "comment": "{ id, postId, authorId, authorName, body, createdAt, canDelete }",
    "session": "{ id, groupId, groupName, groupColor, createdBy, createdByName, title, startsAt, durationMin, meetingLink, goingCount, maybeCount, myRsvp, createdAt, updatedAt }",
    "notification": "{ id, userId, type, message, link, isRead, createdAt }",
}


def flask_path(path: str) -> str:
    """'/api/groups/{group_id}' -> '/api/groups/<group_id>' (the form Flask reports)."""
    return path.replace("{", "<").replace("}", ">")
