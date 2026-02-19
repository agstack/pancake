
import unittest
import os
import sys
from unittest.mock import patch, MagicMock

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
IMPLEMENTATION_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..'))

if IMPLEMENTATION_DIR not in sys.path:
    sys.path.insert(0, IMPLEMENTATION_DIR)

from tap_adapters.johndeere_adapter import JohnDeereAdapter

class TestJohnDeereAdapter(unittest.TestCase):
    def setUp(self):
        self.config = {
            "vendor_name": "johndeere", 
            "base_url": "https://api.deere.com/platform",
            "client_id": "test_id",
            "client_secret": "test_secret"
        }
        self.adapter = JohnDeereAdapter(self.config)

    @patch('tap_adapters.johndeere_adapter.JohnDeereAdapter.load_registry')
    @patch('requests.get')
    def test_machine_mapping_and_bite(self, mock_get, mock_registry):
        #Mock the registry so it doesn't look for a real file
        mock_registry.return_value = {
            "TEST_FARMER": {"access_token": "fake_token"}
        }

        #Mock Organization Response
        mock_orgs = MagicMock()
        mock_orgs.status_code = 200
        mock_orgs.json.return_value = {"values": [{"id": "708", "name": "POC"}]}
        
        #Mock Machines Response
        mock_machines = MagicMock()
        mock_machines.status_code = 200
        mock_machines.json.return_value = {"values": [{"id": "m1", "modelName": "8R", "vin": "JD123"}]}
        
        # requests.get is called twice: once for orgs, once for machines
        mock_get.side_effect = [mock_orgs, mock_machines]

        #Run the function
        bite = self.adapter.fetch_and_transform(
            geoid="FIELD_1", 
            sirup_type="custom", 
            params={"farmer_id": "TEST_FARMER"}
        )
        
        #Assertions
        self.assertIsNotNone(bite, "Bite should not be None")
        assets = bite["Body"]["sirup_data"]["assets"]
        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0]["serial_number"], "JD123")

if __name__ == "__main__":
    unittest.main()
