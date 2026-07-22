"""
Test for bartender functionality
"""

from django.test import Client, TestCase
from django.urls import reverse


class BartenderTest(TestCase):
    """Test bartender endpoint functionality"""

    def test_bartender_endpoint_response(self):
        """Test that the bartender endpoint responds to POST requests"""
        client = Client()
        response = client.post(reverse('bartender'))
        self.assertEqual(response.status_code, 200)

    def test_bartender_returns_correct_json(self):
        """Test that the bartender returns correct JSON with temperature: 40"""
        client = Client()
        response = client.post(reverse('bartender'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"temperature": 40})

    def test_bartender_name_response(self):
        """Optional test: verify bartender name response"""
        client = Client()
        response = client.post(reverse('bartender'))
        response_data = response.json()
        # Check for required field
        self.assertIn('temperature', response_data)
        # Verify temperature value
        self.assertEqual(response_data['temperature'], 40)
