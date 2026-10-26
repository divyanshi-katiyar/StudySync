from .base import ApiTestCase


class ContentCase(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.owner, self.mod, self.member, self.outsider = self.actor("Priya Nair"), self.actor("Mia Mod"), self.actor("Sam Mathew"), self.actor("Out Sider")
        self.g = self.group(self.owner)
        self.joined(self.g, self.mod, self.member)
        self.owner.patch(f"/api/groups/{self.g['id']}/members/{self.mod.id}", json={"role": "moderator"})
        self.gid = self.g["id"]


class ResourceTests(ContentCase):
    def test_add_link_note_and_file(self):
        link = self.member.post(f"/api/groups/{self.gid}/resources", json={"title": "Graph sheet", "type": "link", "url": "https://example.com/a", "tags": ["Graphs", "#Notes"]})
        note = self.member.post(f"/api/groups/{self.gid}/resources", json={"title": "Big-O notes", "type": "note", "body": "O(n) means one pass over the data."})
        file_ = self.member.post(f"/api/groups/{self.gid}/resources", json={"title": "Mock test", "type": "file", "url": "https://example.com/m.pdf"})
        self.assertEqual([r.status_code for r in (link, note, file_)], [201, 201, 201])
        self.assertEqual(link.get_json()["data"]["tags"], ["graphs", "notes"])
        self.assertEqual(note.get_json()["data"]["url"], "")
        self.assertEqual(note.get_json()["data"]["uploaderName"], "Sam Mathew")

    def test_validation(self):
        url = f"/api/groups/{self.gid}/resources"
        self.assertEqual(self.member.post(url, json={"title": "ab", "type": "link", "url": "https://x.co"}).status_code, 422)
        self.assertEqual(self.member.post(url, json={"title": "Fine title", "type": "video", "url": "https://x.co"}).status_code, 422)
        for bad in ("javascript:alert(1)", "ftp://example.com/f", "example.com/notes", "https://"):
            res = self.member.post(url, json={"title": "Fine title", "type": "link", "url": bad})
            self.assertEqual(res.status_code, 422, bad)
            self.assertIn("url", res.get_json()["errors"])
        self.assertEqual(self.member.post(url, json={"title": "Fine title", "type": "note", "body": "short"}).status_code, 422)
        self.assertEqual(self.member.post(url, json={"title": "Fine title", "type": "link", "url": "https://x.co", "tags": "graphs"}).status_code, 422)

    def test_tags_are_cleaned_deduplicated_and_capped(self):
        res = self.member.post(f"/api/groups/{self.gid}/resources", json={"title": "Tagged", "type": "link", "url": "https://x.co", "tags": ["A b", "a-b", "<script>", "#x", "t1", "t2", "t3", "t4", "t5"]})
        tags = res.get_json()["data"]["tags"]
        self.assertEqual(len(tags), 6)
        self.assertIn("a-b", tags)
        self.assertIn("script", tags)  # characters like < > are stripped, never stored
        self.assertEqual(len([t for t in tags if t == "a-b"]), 1)

    def test_only_members_can_read_or_add(self):
        url = f"/api/groups/{self.gid}/resources"
        self.assertEqual(self.outsider.get(url).status_code, 403)
        self.assertEqual(self.outsider.post(url, json={"title": "Sneaky", "type": "link", "url": "https://x.co"}).status_code, 403)
        self.assertEqual(self.owner.get("/api/groups/g_missing/resources").status_code, 404)

    def test_list_filters_and_can_delete_flag(self):
        self.resource(self.member, self.g, "Graph cheat-sheet", tags=["graphs"])
        self.member.post(f"/api/groups/{self.gid}/resources", json={"title": "Sorting notes", "type": "note", "body": "Merge sort splits then merges.", "tags": ["sorting"]})
        url = f"/api/groups/{self.gid}/resources"
        titles = lambda q: [r["title"] for r in self.owner.get(url + q).get_json()["data"]]  # noqa: E731
        self.assertEqual(titles(""), ["Sorting notes", "Graph cheat-sheet"])  # newest first
        self.assertEqual(titles("?type=note"), ["Sorting notes"])
        self.assertEqual(titles("?search=graph"), ["Graph cheat-sheet"])
        self.assertEqual(titles("?search=sorting"), ["Sorting notes"])  # matches tags too
        self.assertEqual(titles("?tag=graphs"), ["Graph cheat-sheet"])
        self.assertEqual(self.owner.get(url + "?type=bogus").status_code, 422)
        res = self.member.get(url)
        self.assertEqual(res.headers["X-Total-Count"], "2")
        self.assertTrue(all(r["canDelete"] for r in res.get_json()["data"]))
        self.assertTrue(all(r["canDelete"] for r in self.owner.get(url).get_json()["data"]))  # staff can delete anything
        self.assertTrue(all(not r["canDelete"] for r in self.outsider_member().get(url).get_json()["data"]))

    def outsider_member(self):
        other = self.actor("Plain Member")
        self.joined(self.g, other)
        return other

    def test_delete_rules(self):
        r = self.resource(self.member, self.g)
        other = self.outsider_member()
        self.assertEqual(other.delete(f"/api/resources/{r['id']}").status_code, 403)
        self.assertEqual(self.outsider.delete(f"/api/resources/{r['id']}").status_code, 403)
        self.assertEqual(self.mod.delete(f"/api/resources/{r['id']}").status_code, 200)
        self.assertEqual(self.mod.delete(f"/api/resources/{r['id']}").status_code, 404)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM resource_tags")[0][0], 0)  # tags went with it

    def test_uploader_can_delete_and_edit_own_resource(self):
        r = self.resource(self.member, self.g)
        res = self.member.patch(f"/api/resources/{r['id']}", json={"title": "Better title", "tags": ["dp"]})
        data = res.get_json()["data"]
        self.assertEqual((data["title"], data["tags"]), ("Better title", ["dp"]))
        self.assertIsNotNone(data["updatedAt"])
        self.assertEqual(self.owner.patch(f"/api/resources/{r['id']}", json={}).status_code, 422)
        self.assertEqual(self.outsider_member().patch(f"/api/resources/{r['id']}", json={"title": "Hijacked"}).status_code, 403)
        self.assertEqual(self.member.delete(f"/api/resources/{r['id']}").status_code, 200)

    def test_sharing_notifies_everyone_else(self):
        self.resource(self.member, self.g)
        for user, expected in ((self.owner, 1), (self.mod, 1), (self.member, 0)):
            notes = [n for n in user.get("/api/notifications").get_json()["data"] if n["type"] == "resource"]
            self.assertEqual(len(notes), expected)
        n = self.owner.get("/api/notifications").get_json()["data"][0]
        self.assertEqual(n["link"], f"/app/groups/{self.gid}?tab=resources")
        self.assertIn("Sam Mathew shared a new resource", n["message"])


class PostTests(ContentCase):
    def test_create_list_and_get_with_comments(self):
        p = self.post_(self.member, self.g)
        self.assertTrue(p["canEdit"])
        c = self.owner.post(f"/api/posts/{p['id']}/comments", json={"body": "Use BFS for shortest paths."})
        self.assertEqual(c.status_code, 201)
        listing = self.owner.get(f"/api/groups/{self.gid}/posts").get_json()["data"]
        self.assertEqual((listing[0]["title"], listing[0]["commentCount"], listing[0]["canEdit"]), ("BFS or DFS here?", 1, False))
        full = self.owner.get(f"/api/posts/{p['id']}").get_json()["data"]
        self.assertEqual(full["group"], {"id": self.gid, "name": self.g["name"]})
        self.assertEqual(full["comments"][0]["authorName"], "Priya Nair")

    def test_validation_and_membership(self):
        url = f"/api/groups/{self.gid}/posts"
        self.assertEqual(self.member.post(url, json={"title": "Hi", "body": "A body that is long enough."}).status_code, 422)
        self.assertEqual(self.member.post(url, json={"title": "A fine title", "body": "short"}).status_code, 422)
        self.assertEqual(self.outsider.post(url, json={"title": "A fine title", "body": "A body that is long enough."}).status_code, 403)
        p = self.post_(self.member, self.g)
        self.assertEqual(self.outsider.get(f"/api/posts/{p['id']}").status_code, 403)
        self.assertEqual(self.outsider.post(f"/api/posts/{p['id']}/comments", json={"body": "hello there"}).status_code, 403)
        self.assertEqual(self.owner.get("/api/posts/p_missing").status_code, 404)

    def test_new_post_notifies_members_and_reply_notifies_the_author(self):
        p = self.post_(self.member, self.g)
        self.assertEqual([n["type"] for n in self.owner.get("/api/notifications").get_json()["data"] if n["type"] == "post"], ["post"])
        self.owner.post(f"/api/posts/{p['id']}/comments", json={"body": "Good question!"})
        mine = self.member.get("/api/notifications").get_json()["data"]
        self.assertEqual([n["type"] for n in mine], ["reply"])
        self.assertEqual(mine[0]["link"], f"/app/groups/{self.gid}/posts/{p['id']}")
        self.member.post(f"/api/posts/{p['id']}/comments", json={"body": "Replying to myself"})
        self.assertEqual(len(self.member.get("/api/notifications").get_json()["data"]), 1)  # no self-notification

    def test_edit_is_author_only_delete_allows_moderators(self):
        p = self.post_(self.member, self.g)
        self.assertEqual(self.member.patch(f"/api/posts/{p['id']}", json={"title": "A new title"}).status_code, 200)
        self.assertEqual(self.owner.patch(f"/api/posts/{p['id']}", json={"title": "Staff edit"}).status_code, 403)
        self.assertEqual(self.member.patch(f"/api/posts/{p['id']}", json={}).status_code, 422)
        self.assertEqual(self.mod.delete(f"/api/posts/{p['id']}").status_code, 200)
        self.assertEqual(self.member.get(f"/api/posts/{p['id']}").status_code, 404)

    def test_comment_rules(self):
        p = self.post_(self.member, self.g)
        self.assertEqual(self.owner.post(f"/api/posts/{p['id']}/comments", json={"body": "x"}).status_code, 422)
        c = self.owner.post(f"/api/posts/{p['id']}/comments", json={"body": "A helpful reply"}).get_json()["data"]
        self.assertEqual(self.member.delete(f"/api/comments/{c['id']}").status_code, 403)
        self.assertEqual(self.mod.delete(f"/api/comments/{c['id']}").status_code, 200)
        self.assertEqual(self.mod.delete(f"/api/comments/{c['id']}").status_code, 404)

    def test_stored_text_is_returned_as_data_not_markup(self):
        p = self.member.post(f"/api/groups/{self.gid}/posts", json={"title": "<script>alert(1)</script>", "body": "<img src=x onerror=alert(1)> payload text"}).get_json()["data"]
        again = self.owner.get(f"/api/posts/{p['id']}")
        self.assertEqual(again.get_json()["data"]["title"], "<script>alert(1)</script>")  # stored verbatim; the client escapes on render
        self.assertTrue(again.content_type.startswith("application/json"))
        self.assertEqual(again.headers["X-Content-Type-Options"], "nosniff")
