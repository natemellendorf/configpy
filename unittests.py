import redis
import unittest
import requests

db = '127.0.0.1'

class TestUM(unittest.TestCase):

    def test_connect_to_db(self):
        r = redis.StrictRedis(host=db, port=6379, db=0)
        self.assertTrue(r.ping())

    def test_add_key_to_db(self):
        r = redis.StrictRedis(host=db, port=6379, db=0)
        device_add = r.hmset('ut_12345', {'device_sn': 'ut_12345', 'hostname': 'unittest-device-isp1', 'config': 'compliant'})
        self.assertTrue(device_add)

    def test_verify_api(self):
        r = requests.get('http://127.0.0.1:8080/hub/device/ut_12345')
        retuned = r.json()
        self.assertEqual(retuned['hostname'], 'unittest-device-isp1')

if __name__ == '__main__':
    unittest.main()
