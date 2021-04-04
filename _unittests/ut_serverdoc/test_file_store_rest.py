"""
@brief      test log(time=1s)

"""
import unittest
import os
import pandas
from pyquickhelper.pycode import ExtTestCase, get_temp_folder
from pyquickhelper.server.filestore_fastapi import create_fast_api_app
from fastapi.testclient import TestClient  # pylint: disable=E0401


class TestfileStoreRest(ExtTestCase):

    def test_file_store(self):
        temp = get_temp_folder(__file__, "temp_file_storage_rest")
        name = os.path.join(temp, "filestore.db3")
        app = create_fast_api_app(name, "BBB")
        client = TestClient(app)
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {'pyquickhelper': 'FastAPI to load and query files'})
        response = client.put(
            "/add/", json=dict(name="essai", content="a,b\ne,0\nhh, 1.5",
                               password="CCC"))
        self.assertEqual(response.status_code, 401)
        response = client.put(
            "/add/", json=dict(name="essai", content="a,b\ne,0\nhh, 1.5",
                               password="BBB"))
        self.assertEqual(response.status_code, 200)
        js = response.json()
        self.assertIn('date', js)
        self.assertNotIn('content', js)


if __name__ == "__main__":
    unittest.main()
