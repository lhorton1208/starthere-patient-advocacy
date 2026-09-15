"""Unit tests for FHIR JWT assertion, mapping, and live client wiring."""

from __future__ import annotations

import base64
import json
import os
import unittest
from unittest import mock

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from fhir.client import LiveFHIRClient
from fhir.jwt_assert import create_client_assertion
from fhir.jwks import clear_jwks_cache
from fhir.mapping import map_encounters, map_observations, patient_display_name
from fhir.oauth import request_private_key_jwt_token


def _rsa_pem() -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


class JwtAssertTests(unittest.TestCase):
    def test_create_client_assertion_structure(self):
        pem = _rsa_pem()
        token = create_client_assertion(
            client_id="client-123",
            token_url="https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token",
            private_key_pem=pem,
            algorithm="RS384",
            kid="kid-1",
        )
        header_b64, payload_b64, signature_b64 = token.split(".")
        header = json.loads(base64.urlsafe_b64decode(header_b64 + "=="))
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=="))
        self.assertEqual(header["alg"], "RS384")
        self.assertEqual(header["kid"], "kid-1")
        self.assertEqual(payload["iss"], "client-123")
        self.assertEqual(payload["sub"], "client-123")
        self.assertEqual(
            payload["aud"],
            "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token",
        )
        self.assertLessEqual(payload["exp"] - payload["iat"], 300)
        self.assertTrue(signature_b64)


class MappingTests(unittest.TestCase):
    def test_patient_display_name(self):
        patient = {
            "resourceType": "Patient",
            "id": "abc",
            "name": [{"use": "usual", "family": "Cancer", "given": ["Test"]}],
        }
        self.assertEqual(patient_display_name(patient), "Test Cancer")

    def test_map_observations(self):
        bundle = {
            "resourceType": "Bundle",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Observation",
                        "id": "obs1",
                        "status": "final",
                        "category": [{"text": "Laboratory"}],
                        "code": {"text": "Glucose"},
                        "effectiveDateTime": "2019-06-10",
                        "valueQuantity": {"value": 138, "unit": "mg/dL"},
                    }
                }
            ],
        }
        results = map_observations(bundle)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Glucose")
        self.assertEqual(results[0].result_summary, "138 mg/dL")

    def test_map_encounters(self):
        bundle = {
            "resourceType": "Bundle",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Encounter",
                        "id": "enc1",
                        "status": "finished",
                        "type": [{"text": "Office visit"}],
                        "period": {"start": "2020-01-02T10:00:00Z"},
                    }
                }
            ],
        }
        items = map_encounters(bundle)
        self.assertEqual(items[0].encounter_type, "Office visit")
        self.assertEqual(items[0].when, "2020-01-02T10:00:00Z")


class PrivateKeyJwtTokenTests(unittest.TestCase):
    def test_token_request_posts_assertion(self):
        pem = _rsa_pem()

        class FakeResponse:
            def read(self):
                return json.dumps(
                    {"access_token": "tok-abc", "token_type": "bearer", "expires_in": 3600}
                ).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with mock.patch("fhir.oauth.urllib.request.urlopen", return_value=FakeResponse()) as urlopen:
            result = request_private_key_jwt_token(
                token_url="https://example.com/oauth2/token",
                client_id="cid",
                private_key_pem=pem,
                scope="system/*.read",
                algorithm="RS384",
                kid="k1",
            )

        self.assertEqual(result.access_token, "tok-abc")
        request = urlopen.call_args[0][0]
        body = request.data.decode("utf-8")
        self.assertIn("grant_type=client_credentials", body)
        self.assertIn(
            "client_assertion_type=urn%3Aietf%3Aparams%3Aoauth%3Aclient-assertion-type%3Ajwt-bearer",
            body,
        )
        self.assertIn("client_assertion=", body)
        self.assertIn("scope=system%2F%2A.read", body)


class LiveClientTests(unittest.TestCase):
    def setUp(self):
        clear_jwks_cache()
        self.pem = _rsa_pem()
        self.env = {
            "PORTAL_JWT_PRIVATE_KEY": self.pem.decode("ascii"),
            "PORTAL_JWT_ALG": "RS384",
            "PORTAL_JWT_KID": "test-kid",
            "PUBLIC_BASE_URL": "https://portal.example",
        }
        self._patcher = mock.patch.dict(os.environ, self.env, clear=False)
        self._patcher.start()
        clear_jwks_cache()

    def tearDown(self):
        self._patcher.stop()
        clear_jwks_cache()

    def test_fetch_dashboard_live_mapping(self):
        client = LiveFHIRClient(
            "https://fhir.example/r4",
            token_url="https://fhir.example/oauth2/token",
            client_id="cid",
            default_patient_id="pat-1",
        )

        def fake_obtain():
            client._auth_method = "private_key_jwt"
            return "access-token"

        responses = {
            "Patient/pat-1": {
                "resourceType": "Patient",
                "id": "pat-1",
                "name": [{"text": "Camila Lopez"}],
            },
            "Observation": {
                "resourceType": "Bundle",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "Observation",
                            "id": "o1",
                            "status": "final",
                            "code": {"text": "HbA1c"},
                            "valueQuantity": {"value": 7.6, "unit": "%"},
                            "effectiveDateTime": "2019-06-10",
                        }
                    }
                ],
            },
            "Encounter": {"resourceType": "Bundle", "entry": []},
            "Coverage": {"resourceType": "Bundle", "entry": []},
            "Procedure": {"resourceType": "Bundle", "entry": []},
        }

        def fake_get(path_or_url, access_token):
            self.assertEqual(access_token, "access-token")
            for key, payload in responses.items():
                if key in path_or_url:
                    return payload
            self.fail(f"Unexpected URL: {path_or_url}")

        with mock.patch.object(client, "_obtain_access_token", side_effect=fake_obtain):
            with mock.patch.object(client, "_safe_get", side_effect=fake_get):
                dashboard = client.fetch_dashboard()

        self.assertEqual(dashboard.connection.mode, "live")
        self.assertEqual(dashboard.patient_display_name, "Camila Lopez")
        self.assertEqual(len(dashboard.test_results), 1)
        self.assertEqual(dashboard.test_results[0].name, "HbA1c")


if __name__ == "__main__":
    unittest.main()
