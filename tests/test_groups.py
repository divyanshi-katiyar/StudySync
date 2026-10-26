from .base import ApiTestCase


class CreateAndReadTests(ApiTestCase):
    def test_create_makes_the_creator_owner_and_returns_an_invite_code(self):
        a = self.actor("Priya Nair")
        res = a.post("/api/groups", json={"name": "  Algorithms Circle ", "description": "Weekly problem solving.", "subject": "Data Structures", "visibility": "public"})
        g = res.get_json()["data"]
        self.assertEqual(res.status_code, 201)
        self.assertEqual((g["name"], g["myRole"], g["memberCount"], g["ownerName"]), ("Algorithms Circle", "owner", 1, "Priya Nair"))
        self.assertRegex(g["inviteCode"], r"^DAT-[A-Z2-9]{6}$")
        self.assertEqual(g["color"], "#0F7B70")

    def test_create_validation(self):
        a = self.actor()
        res = a.post("/api/groups", json={"name": "ab", "description": "short", "subject": "Basket Weaving", "visibility": "secret"})
        self.assertEqual(res.status_code, 422)
        self.assertEqual(set(res.get_json()["errors"]), {"name", "description", "subject", "visibility"})

    def test_invite_codes_are_unique(self):
        a = self.actor()
        codes = {self.group(a, name=f"Group number {i}")["inviteCode"] for i in range(15)}
        self.assertEqual(len(codes), 15)

    def test_public_group_preview_hides_the_invite_code(self):
        owner, stranger = self.actor(), self.actor()
        g = self.group(owner)
        seen = stranger.get(f"/api/groups/{g['id']}").get_json()["data"]
        self.assertFalse(seen["isMember"])
        self.assertNotIn("inviteCode", seen)
        self.assertIn("inviteCode", owner.get(f"/api/groups/{g['id']}").get_json()["data"])

    def test_private_group_is_403_for_outsiders_but_open_to_members(self):
        owner, stranger = self.actor(), self.actor()
        g = self.group(owner, visibility="private")
        self.assertEqual(stranger.get(f"/api/groups/{g['id']}").status_code, 403)
        self.joined(g, stranger)
        self.assertEqual(stranger.get(f"/api/groups/{g['id']}").status_code, 200)

    def test_missing_group_is_404(self):
        self.assertEqual(self.actor().get("/api/groups/g_missing").status_code, 404)

    def test_mine_lists_only_my_groups_sorted_by_name(self):
        a, b = self.actor(), self.actor()
        self.group(a, name="Zeta group"); self.group(a, name="Alpha group"); self.group(b, name="Not mine")
        names = [g["name"] for g in a.get("/api/groups/mine").get_json()["data"]]
        self.assertEqual(names, ["Alpha group", "Zeta group"])

    def test_groups_require_login(self):
        self.assertEqual(self.app.test_client().get("/api/groups").status_code, 401)


class DiscoverTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.a, self.b = self.actor(), self.actor()
        self.group(self.a, name="Graph Theory Club", subject="Data Structures")
        self.group(self.a, name="SQL Practice", subject="Databases", description="Joins, indexes and normalisation drills.")
        self.group(self.a, name="Secret Society", subject="Databases", visibility="private")
        self.group(self.a, name="100% Effort Group", subject="Placements")

    def discover(self, query=""):
        return self.b.get("/api/groups" + query).get_json()["data"]

    def test_private_groups_never_appear(self):
        names = [g["name"] for g in self.discover()["items"]]
        self.assertNotIn("Secret Society", names)
        self.assertEqual(self.discover()["total"], 3)

    def test_search_matches_name_subject_and_description(self):
        self.assertEqual([g["name"] for g in self.discover("?search=graph")["items"]], ["Graph Theory Club"])
        self.assertEqual([g["name"] for g in self.discover("?search=databases")["items"]], ["SQL Practice"])
        self.assertEqual([g["name"] for g in self.discover("?search=normalisation")["items"]], ["SQL Practice"])

    def test_search_treats_percent_and_underscore_literally(self):
        self.assertEqual([g["name"] for g in self.discover("?search=%25")["items"]], ["100% Effort Group"])
        self.assertEqual(self.discover("?search=_")["total"], 0)

    def test_sql_injection_in_search_returns_nothing_and_breaks_nothing(self):
        self.assertEqual(self.discover("?search=' OR 1=1 --")["total"], 0)
        self.assertEqual(self.discover("?search=x'; DROP TABLE users; --")["total"], 0)
        self.assertEqual(self.b.get("/api/users/me").status_code, 200)

    def test_subject_filter(self):
        self.assertEqual(self.discover("?subject=Databases")["total"], 1)

    def test_sort_by_popularity_and_newest(self):
        g = self.discover()["items"][0]
        c = self.actor()
        popular_first = self.group(self.a, name="Popular group")
        self.joined(popular_first, self.b, c)
        self.assertEqual(self.discover("?sort=popular")["items"][0]["name"], "Popular group")
        self.assertEqual(self.discover("?sort=newest")["items"][0]["name"], "Popular group")
        self.assertEqual(self.b.get("/api/groups?sort=bogus").status_code, 422)

    def test_pagination(self):
        page1 = self.discover("?limit=2&page=1")
        page2 = self.discover("?limit=2&page=2")
        self.assertEqual((len(page1["items"]), page1["total"], page1["pages"]), (2, 3, 2))
        self.assertEqual(len(page2["items"]), 1)
        self.assertEqual(self.discover("?limit=2&page=99")["page"], 2)  # clamped to the last page
        self.assertEqual(self.b.get("/api/groups?page=abc").status_code, 422)
        self.assertEqual(len(self.discover("?limit=1000")["items"]), 3)  # limit is capped, not an error


class MembershipTests(ApiTestCase):
    def test_join_public_group(self):
        owner, user = self.actor(), self.actor()
        g = self.group(owner)
        res = user.post(f"/api/groups/{g['id']}/join")
        data = res.get_json()["data"]
        self.assertEqual((res.status_code, data["myRole"], data["memberCount"]), (200, "member", 2))

    def test_join_twice_is_409_and_private_join_is_403(self):
        owner, user = self.actor(), self.actor()
        pub, priv = self.group(owner), self.group(owner, name="Private one", visibility="private")
        user.post(f"/api/groups/{pub['id']}/join")
        self.assertEqual(user.post(f"/api/groups/{pub['id']}/join").status_code, 409)
        self.assertEqual(user.post(f"/api/groups/{priv['id']}/join").status_code, 403)
        self.assertEqual(user.post("/api/groups/g_missing/join").status_code, 404)

    def test_join_by_code(self):
        owner, user = self.actor(), self.actor()
        g = self.group(owner, visibility="private")
        c = user.client
        self.assertEqual(user.post("/api/groups/join-by-code", json={"code": ""}).status_code, 422)
        self.assertEqual(user.post("/api/groups/join-by-code", json={"code": "NOPE-000000"}).status_code, 404)
        ok = user.post("/api/groups/join-by-code", json={"code": g["inviteCode"].lower()})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(user.post("/api/groups/join-by-code", json={"code": g["inviteCode"]}).status_code, 409)

    def test_joining_notifies_the_other_members_only(self):
        owner, user = self.actor("Priya Nair"), self.actor("Sam Mathew")
        g = self.group(owner)
        user.post(f"/api/groups/{g['id']}/join")
        mine = owner.get("/api/notifications").get_json()["data"]
        self.assertEqual([n["type"] for n in mine], ["member"])
        self.assertIn("Sam Mathew joined", mine[0]["message"])
        self.assertEqual(user.get("/api/notifications").get_json()["data"], [])

    def test_leave(self):
        owner, user = self.actor(), self.actor()
        g = self.group(owner)
        self.joined(g, user)
        self.assertEqual(user.delete(f"/api/groups/{g['id']}/leave").status_code, 200)
        self.assertEqual(user.delete(f"/api/groups/{g['id']}/leave").status_code, 403)  # no longer a member
        self.assertEqual(owner.delete(f"/api/groups/{g['id']}/leave").status_code, 409)  # owners cannot just leave

    def test_members_list_is_ordered_by_role(self):
        owner, mod, member = self.actor("Zed Owner"), self.actor("Mia Mod"), self.actor("Ann Member")
        g = self.group(owner)
        self.joined(g, mod, member)
        owner.patch(f"/api/groups/{g['id']}/members/{mod.id}", json={"role": "moderator"})
        rows = owner.get(f"/api/groups/{g['id']}/members").get_json()["data"]
        self.assertEqual([(r["name"], r["role"]) for r in rows], [("Zed Owner", "owner"), ("Mia Mod", "moderator"), ("Ann Member", "member")])

    def test_members_list_is_private_to_members(self):
        owner, stranger = self.actor(), self.actor()
        g = self.group(owner)
        self.assertEqual(stranger.get(f"/api/groups/{g['id']}/members").status_code, 403)


class RoleTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.owner, self.mod, self.m1, self.m2 = self.actor(), self.actor(), self.actor(), self.actor()
        self.g = self.group(self.owner)
        self.joined(self.g, self.mod, self.m1, self.m2)
        self.base = f"/api/groups/{self.g['id']}/members"
        self.owner.patch(f"{self.base}/{self.mod.id}", json={"role": "moderator"})

    def test_only_the_owner_changes_roles(self):
        self.assertEqual(self.mod.patch(f"{self.base}/{self.m1.id}", json={"role": "moderator"}).status_code, 403)
        self.assertEqual(self.owner.patch(f"{self.base}/{self.m1.id}", json={"role": "moderator"}).status_code, 200)

    def test_role_must_be_valid_and_the_owner_cannot_be_changed(self):
        self.assertEqual(self.owner.patch(f"{self.base}/{self.m1.id}", json={"role": "owner"}).status_code, 422)
        self.assertEqual(self.owner.patch(f"{self.base}/{self.owner.id}", json={"role": "member"}).status_code, 404)
        self.assertEqual(self.owner.patch(f"{self.base}/u_nobody", json={"role": "member"}).status_code, 404)

    def test_removal_rules(self):
        self.assertEqual(self.m1.delete(f"{self.base}/{self.m2.id}").status_code, 403)  # members cannot remove anyone
        self.assertEqual(self.mod.delete(f"{self.base}/{self.owner.id}").status_code, 404)  # nobody removes the owner
        self.assertEqual(self.mod.delete(f"{self.base}/{self.m1.id}").status_code, 200)  # moderators remove members
        self.owner.patch(f"{self.base}/{self.m2.id}", json={"role": "moderator"})
        self.assertEqual(self.mod.delete(f"{self.base}/{self.m2.id}").status_code, 403)  # ...but not other moderators
        self.assertEqual(self.owner.delete(f"{self.base}/{self.m2.id}").status_code, 200)  # the owner removes anyone else

    def test_transfer_ownership(self):
        url = f"/api/groups/{self.g['id']}/transfer-ownership"
        self.assertEqual(self.mod.post(url, json={"userId": self.m1.id}).status_code, 403)
        self.assertEqual(self.owner.post(url, json={"userId": self.owner.id}).status_code, 422)
        self.assertEqual(self.owner.post(url, json={"userId": self.actor().id}).status_code, 422)  # not a member
        res = self.owner.post(url, json={"userId": self.m1.id})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["data"]["myRole"], "moderator")
        self.assertEqual(self.m1.get(f"/api/groups/{self.g['id']}").get_json()["data"]["myRole"], "owner")
        self.assertEqual(self.owner.delete(f"/api/groups/{self.g['id']}/leave").status_code, 200)  # the old owner can now leave

    def test_database_allows_only_one_owner(self):
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):
            self.sql("UPDATE memberships SET role = 'owner' WHERE user_id = ?", (self.m1.id,))


class UpdateAndDeleteTests(ApiTestCase):
    def test_owner_edits_group(self):
        owner = self.actor()
        g = self.group(owner)
        res = owner.patch(f"/api/groups/{g['id']}", json={"name": "Renamed group", "visibility": "private"})
        data = res.get_json()["data"]
        self.assertEqual((data["name"], data["visibility"]), ("Renamed group", "private"))

    def test_edit_is_owner_only_and_validated(self):
        owner, mod = self.actor(), self.actor()
        g = self.group(owner)
        self.joined(g, mod)
        owner.patch(f"/api/groups/{g['id']}/members/{mod.id}", json={"role": "moderator"})
        self.assertEqual(mod.patch(f"/api/groups/{g['id']}", json={"name": "Hijacked"}).status_code, 403)
        self.assertEqual(owner.patch(f"/api/groups/{g['id']}", json={"name": "x"}).status_code, 422)
        self.assertEqual(owner.patch(f"/api/groups/{g['id']}", json={"invite_code": "HACK"}).status_code, 422)  # unknown fields are ignored

    def test_delete_removes_everything_in_the_group(self):
        owner, user = self.actor(), self.actor()
        g = self.group(owner)
        self.joined(g, user)
        self.resource(owner, g); p = self.post_(owner, g); self.session(owner, g)
        user.post(f"/api/posts/{p['id']}/comments", json={"body": "Nice question"})
        self.assertEqual(user.delete(f"/api/groups/{g['id']}").status_code, 403)
        self.assertEqual(owner.delete(f"/api/groups/{g['id']}").status_code, 200)
        for table in ("memberships", "resources", "resource_tags", "posts", "comments", "study_sessions", "session_attendees"):
            self.assertEqual(self.sql(f"SELECT COUNT(*) FROM {table}")[0][0], 0, table)
        self.assertEqual(owner.get(f"/api/groups/{g['id']}").status_code, 404)

    def test_outsider_cannot_delete(self):
        owner, stranger = self.actor(), self.actor()
        g = self.group(owner)
        self.assertEqual(stranger.delete(f"/api/groups/{g['id']}").status_code, 403)
