from .base import ApiTestCase


class SessionCase(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.owner, self.mod, self.member, self.outsider = self.actor("Priya Nair"), self.actor("Mia Mod"), self.actor("Sam Mathew"), self.actor("Out Sider")
        self.g = self.group(self.owner)
        self.joined(self.g, self.mod, self.member)
        self.owner.patch(f"/api/groups/{self.g['id']}/members/{self.mod.id}", json={"role": "moderator"})
        self.url = f"/api/groups/{self.g['id']}/sessions"


class SessionTests(SessionCase):
    def test_staff_can_schedule_and_the_organiser_is_going(self):
        res = self.mod.post(self.url, json={"title": "Graph problems", "startsAt": self.in_hours(24), "durationMin": 90, "meetingLink": "https://meet.example.com/g"})
        s = res.get_json()["data"]
        self.assertEqual((res.status_code, s["durationMin"], s["goingCount"], s["myRsvp"], s["groupName"]), (201, 90, 1, "going", self.g["name"]))
        self.assertTrue(s["startsAt"].endswith("Z"))

    def test_plain_members_and_outsiders_cannot_schedule(self):
        body = {"title": "Graph problems", "startsAt": self.in_hours(24), "durationMin": 60}
        self.assertEqual(self.member.post(self.url, json=body).status_code, 403)
        self.assertEqual(self.outsider.post(self.url, json=body).status_code, 403)

    def test_validation(self):
        bad = self.owner.post(self.url, json={"title": "ab", "startsAt": self.in_hours(-2), "durationMin": 5, "meetingLink": "not a link"})
        self.assertEqual(bad.status_code, 422)
        self.assertEqual(set(bad.get_json()["errors"]), {"title", "startsAt", "durationMin", "meetingLink"})
        self.assertEqual(self.owner.post(self.url, json={"title": "Fine title", "startsAt": "tomorrow-ish", "durationMin": 60}).status_code, 422)
        self.assertEqual(self.owner.post(self.url, json={"title": "Fine title", "startsAt": self.in_hours(5), "durationMin": 301}).status_code, 422)
        self.assertEqual(self.owner.post(self.url, json={"title": "Fine title", "startsAt": self.in_hours(5), "durationMin": True}).status_code, 422)

    def test_form_style_values_are_accepted(self):
        res = self.owner.post(self.url, json={"title": "Form session", "startsAt": self.in_hours(5), "durationMin": "60", "meetingLink": ""})
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.get_json()["data"]["durationMin"], 60)

    def test_offset_times_are_stored_as_utc(self):
        res = self.owner.post(self.url, json={"title": "Offset time", "startsAt": "2099-01-01T10:00:00+05:30", "durationMin": 60})
        self.assertEqual(res.get_json()["data"]["startsAt"], "2099-01-01T04:30:00.000Z")

    def test_list_is_members_only_and_ordered(self):
        later, sooner = self.session(self.owner, self.g, "Later", 48), self.session(self.owner, self.g, "Sooner", 10)
        titles = [s["title"] for s in self.member.get(self.url).get_json()["data"]]
        self.assertEqual(titles, ["Sooner", "Later"])
        self.assertEqual(self.outsider.get(self.url).status_code, 403)

    def test_scheduling_notifies_members(self):
        self.session(self.owner, self.g, "Graph problems")
        n = [x for x in self.member.get("/api/notifications").get_json()["data"] if x["type"] == "session"]
        self.assertEqual(len(n), 1)
        self.assertEqual(n[0]["link"], f"/app/groups/{self.g['id']}?tab=sessions")

    def test_update_and_delete_are_staff_only(self):
        s = self.session(self.owner, self.g)
        path = f"/api/sessions/{s['id']}"
        self.assertEqual(self.member.patch(path, json={"title": "Changed"}).status_code, 403)
        res = self.mod.patch(path, json={"title": "Changed title", "durationMin": 45})
        self.assertEqual((res.get_json()["data"]["title"], res.get_json()["data"]["durationMin"]), ("Changed title", 45))
        self.assertEqual(self.owner.patch(path, json={}).status_code, 422)
        self.assertEqual(self.outsider.delete(path).status_code, 403)
        self.assertEqual(self.member.delete(path).status_code, 403)
        self.assertEqual(self.owner.delete(path).status_code, 200)
        self.assertEqual(self.owner.delete(path).status_code, 404)


class RsvpTests(SessionCase):
    def test_rsvp_changes_counts_and_is_idempotent(self):
        s = self.session(self.owner, self.g)
        path = f"/api/sessions/{s['id']}/rsvp"
        first = self.member.put(path, json={"status": "going"}).get_json()["data"]
        self.assertEqual((first["goingCount"], first["myRsvp"]), (2, "going"))
        self.member.put(path, json={"status": "going"})
        again = self.mod.put(path, json={"status": "maybe"}).get_json()["data"]
        self.assertEqual((again["goingCount"], again["maybeCount"], again["myRsvp"]), (2, 1, "maybe"))
        changed = self.member.put(path, json={"status": "no"}).get_json()["data"]
        self.assertEqual((changed["goingCount"], changed["myRsvp"]), (1, "no"))
        self.assertEqual(self.sql("SELECT COUNT(*) FROM session_attendees")[0][0], 3)  # one row per person, never duplicated

    def test_rsvp_validation_and_permissions(self):
        s = self.session(self.owner, self.g)
        path = f"/api/sessions/{s['id']}/rsvp"
        self.assertEqual(self.member.put(path, json={"status": "perhaps"}).status_code, 422)
        self.assertEqual(self.member.put(path, json={}).status_code, 422)
        self.assertEqual(self.outsider.put(path, json={"status": "going"}).status_code, 403)
        self.assertEqual(self.member.put("/api/sessions/s_missing/rsvp", json={"status": "going"}).status_code, 404)


class UpcomingAndDashboardTests(SessionCase):
    def test_upcoming_shows_only_future_sessions_in_my_groups(self):
        self.session(self.owner, self.g, "Soon", 5)
        self.session(self.owner, self.g, "Later", 50)
        other_owner = self.actor()
        other = self.group(other_owner, name="Someone else's group")
        self.session(other_owner, other, "Not for me", 3)
        self.sql("INSERT INTO study_sessions (id, group_id, created_by, title, starts_at, duration_min, created_at) VALUES ('s_past', ?, ?, 'Yesterday', '2020-01-01T00:00:00.000Z', 60, '2020-01-01T00:00:00.000Z')", (self.g["id"], self.owner.id))
        titles = [s["title"] for s in self.member.get("/api/sessions").get_json()["data"]]
        self.assertEqual(titles, ["Soon", "Later"])
        self.assertEqual(self.member.get("/api/sessions?limit=1").get_json()["data"][0]["title"], "Soon")

    def test_notifications_list_and_read(self):
        self.resource(self.owner, self.g, "One"); self.resource(self.owner, self.g, "Two")
        notes = self.member.get("/api/notifications").get_json()["data"]
        self.assertEqual(len(notes), 2)
        one = self.member.patch(f"/api/notifications/{notes[0]['id']}/read").get_json()["data"]
        self.assertTrue(one["isRead"])
        self.assertEqual(len(self.member.get("/api/notifications?unread=true").get_json()["data"]), 1)
        self.assertEqual(self.member.patch("/api/notifications/read-all").get_json()["data"], {"updated": 1})
        self.assertEqual(self.member.get("/api/notifications?unread=true").get_json()["data"], [])

    def test_nobody_can_read_or_mark_someone_elses_notification(self):
        self.resource(self.owner, self.g)
        theirs = self.member.get("/api/notifications").get_json()["data"][0]
        self.assertEqual(self.mod.patch(f"/api/notifications/{theirs['id']}/read").status_code, 404)
        self.assertEqual(self.outsider.get("/api/notifications").get_json()["data"], [])
        self.assertFalse(self.member.get("/api/notifications").get_json()["data"][0]["isRead"])

    def test_dashboard_counts(self):
        self.session(self.owner, self.g, "This week", 24)
        self.session(self.owner, self.g, "Next month", 24 * 20)
        self.resource(self.owner, self.g)
        self.resource(self.member, self.g, "My own")
        d = self.member.get("/api/users/me/dashboard").get_json()["data"]
        self.assertEqual(d["counts"], {"groups": 1, "sessionsThisWeek": 1, "newResources": 1})  # my own upload does not count
        self.assertEqual([s["title"] for s in d["upcomingSessions"]], ["This week", "Next month"])
        self.assertEqual(d["myGroups"][0]["name"], self.g["name"])
        empty = self.outsider.get("/api/users/me/dashboard").get_json()["data"]
        self.assertEqual(empty["counts"], {"groups": 0, "sessionsThisWeek": 0, "newResources": 0})
