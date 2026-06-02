import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from io import BytesIO

from PIL import Image

from src.aussie_ecolens.server import Handler, reset_demo_data
from src.aussie_ecolens.species import tags_from_text


class WorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reset_demo_data()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.thread.join(timeout=5)

    def setUp(self):
        reset_demo_data()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        payload = response.read()
        conn.close()
        data = json.loads(payload.decode("utf-8")) if payload else {}
        return response.status, data

    def json_request(self, path, payload, token=None):
        headers = {"content-type": "application/json"}
        if token:
            headers["authorization"] = f"Bearer {token}"
        return self.request("POST", path, json.dumps(payload), headers)

    def signup_and_signin(self, email):
        status, data = self.json_request(
            "/api/auth/signup",
            {
                "email": email,
                "first_name": "Demo",
                "last_name": "User",
                "password": "Passw0rd!",
            },
        )
        self.assertEqual(status, 200, data)
        status, data = self.json_request(
            "/api/auth/signin",
            {"email": email, "password": "Passw0rd!"},
        )
        self.assertEqual(status, 200, data)
        return data["token"]

    def multipart_request(self, path, filename, data, token, content_type="image/jpeg"):
        boundary = "----aussie-ecolens-test"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8") + data + f"\r\n--{boundary}--\r\n".encode("utf-8")
        return self.request(
            "POST",
            path,
            body,
            {
                "content-type": f"multipart/form-data; boundary={boundary}",
                "content-length": str(len(body)),
                "authorization": f"Bearer {token}",
            },
        )

    def image_bytes(self):
        image = Image.new("RGB", (640, 360), (44, 120, 70))
        buf = BytesIO()
        image.save(buf, "JPEG")
        return buf.getvalue()

    def test_complete_local_workflow(self):
        status, data = self.json_request(
            "/api/auth/signup",
            {
                "email": "demo@example.com",
                "first_name": "Demo",
                "last_name": "User",
                "password": "Passw0rd!",
            },
        )
        self.assertEqual(status, 200, data)

        status, data = self.json_request(
            "/api/auth/signin",
            {"email": "demo@example.com", "password": "Passw0rd!"},
        )
        self.assertEqual(status, 200, data)
        token = data["token"]

        status, data = self.json_request("/api/notifications/watch", {"tags": ["koala"], "email": "demo@example.com"}, token)
        self.assertEqual(status, 200, data)

        image = self.image_bytes()
        status, data = self.multipart_request("/api/upload", "koala2_wombat1.jpg", image, token)
        self.assertEqual(status, 200, data)
        self.assertFalse(data["duplicate"])
        media = data["media"]
        self.assertEqual(media["tags"]["koala"], 2)
        self.assertEqual(media["tags"]["wombat"], 1)
        self.assertTrue(media["thumbnail_url"].endswith(".jpg"))

        status, duplicate = self.multipart_request("/api/upload", "koala2_wombat1.jpg", image, token)
        self.assertEqual(status, 200, duplicate)
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(duplicate["media"]["checksum"], media["checksum"])

        status, query = self.json_request("/api/query/tags", {"tags": {"koala": 2, "wombat": 1}}, token)
        self.assertEqual(status, 200, query)
        self.assertEqual(len(query["results"]), 1)

        status, species = self.json_request("/api/query/species", {"species": "koala"}, token)
        self.assertEqual(status, 200, species)
        self.assertEqual(len(species["results"]), 1)

        status, full = self.json_request("/api/query/thumbnail", {"thumbnail_url": media["thumbnail_url"]}, token)
        self.assertEqual(status, 200, full)
        self.assertEqual(full["full_url"], media["full_url"])

        status, by_file = self.multipart_request("/api/query/file", "koala1.jpg", image, token)
        self.assertEqual(status, 200, by_file)
        self.assertEqual(len(by_file["results"]), 1)

        status, edited = self.json_request(
            "/api/tags/edit",
            {"urls": [media["full_url"]], "tags": ["dingo"], "operation": 1},
            token,
        )
        self.assertEqual(status, 200, edited)

        status, dingo = self.json_request("/api/query/species", {"species": "dingo"}, token)
        self.assertEqual(status, 200, dingo)
        self.assertEqual(len(dingo["results"]), 1)

        status, notifications = self.request("GET", "/api/notifications", headers={"authorization": f"Bearer {token}"})
        self.assertEqual(status, 200, notifications)
        self.assertGreaterEqual(len(notifications["notifications"]), 1)

        status, deleted = self.json_request("/api/delete", {"urls": [media["full_url"]]}, token)
        self.assertEqual(status, 200, deleted)
        self.assertEqual(deleted["deleted"], [media["id"]])

        status, empty = self.json_request("/api/query/species", {"species": "koala"}, token)
        self.assertEqual(status, 200, empty)
        self.assertEqual(empty["results"], [])

    def test_protected_routes_require_authentication(self):
        image = self.image_bytes()

        status, data = self.multipart_request("/api/upload", "koala1.jpg", image, token="")
        self.assertEqual(status, 401, data)
        self.assertEqual(data["error"], "authentication required")

        status, data = self.json_request("/api/query/species", {"species": "koala"})
        self.assertEqual(status, 401, data)
        self.assertEqual(data["error"], "authentication required")

    def test_bulk_tag_remove_ignores_missing_tags(self):
        token = self.signup_and_signin("bulk@example.com")

        image = self.image_bytes() + b"bulk-remove"
        status, upload = self.multipart_request("/api/upload", "dingo1_magpie2.jpg", image, token)
        self.assertEqual(status, 200, upload)
        media = upload["media"]
        self.assertEqual(media["tags"]["dingo"], 1)
        self.assertEqual(media["tags"]["magpie"], 2)

        status, edited = self.json_request(
            "/api/tags/edit",
            {"urls": [media["full_url"]], "tags": ["magpie", "missing_tag"], "operation": 0},
            token,
        )
        self.assertEqual(status, 200, edited)

        status, magpie = self.json_request("/api/query/species", {"species": "magpie"}, token)
        self.assertEqual(status, 200, magpie)
        self.assertFalse(any(item["id"] == media["id"] for item in magpie["results"]))

        status, dingo = self.json_request("/api/query/species", {"species": "dingo"}, token)
        self.assertEqual(status, 200, dingo)
        self.assertTrue(any(item["id"] == media["id"] for item in dingo["results"]))

    def test_video_upload_records_media_type_and_queryable_tags(self):
        token = self.signup_and_signin("video@example.com")

        fake_video = b"not-a-real-video-but-valid-for-local-metadata-test"
        status, upload = self.multipart_request(
            "/api/upload",
            "kangaroo1_demo.mp4",
            fake_video,
            token,
            content_type="video/mp4",
        )
        self.assertEqual(status, 200, upload)
        media = upload["media"]
        self.assertEqual(media["media_type"], "video")
        self.assertIsNone(media["thumbnail_url"])
        self.assertEqual(media["tags"]["kangaroo"], 1)

        status, query = self.json_request("/api/query/tags", {"tags": {"kangaroo": 1}}, token)
        self.assertEqual(status, 200, query)
        self.assertTrue(any(item["id"] == media["id"] for item in query["results"]))


class CourseLabelsTest(unittest.TestCase):
    def test_course_scientific_filenames_are_tags(self):
        self.assertEqual(tags_from_text("Casuarius_casuarius_1.JPG"), {"casuarius_casuarius": 1})
        self.assertEqual(tags_from_text("Hypsiprymnodon_moschatus_2.JPG"), {"hypsiprymnodon_moschatus": 1})


if __name__ == "__main__":
    unittest.main()
