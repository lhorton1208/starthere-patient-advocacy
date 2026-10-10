"""Unit tests for FHIR JWT assertion, mapping, and live client wiring."""

from __future__ import annotations

import base64
import json
import os
import unittest
from unittest import mock

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from fhir.client import (
    DemoFHIRClient,
    EPIC_SANDBOX_TEST_PATIENT_ID,
    LiveFHIRClient,
    normalize_portal_environment,
    resolve_fhir_connection_settings,
)
from fhir.jwt_assert import create_client_assertion
from fhir.jwks import clear_jwks_cache
from fhir.mapping import (
    map_allergies,
    map_diagnoses,
    map_encounters,
    map_medications,
    map_observations,
    map_patient_matches,
    map_problems,
    map_provider_notes,
    patient_display_name,
)
from fhir.oauth import request_private_key_jwt_token


def _rsa_pem() -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


class PortalEnvironmentTests(unittest.TestCase):
    def test_normalize_portal_environment(self):
        self.assertEqual(normalize_portal_environment("sandbox"), "sandbox")
        self.assertEqual(normalize_portal_environment("nonprod"), "sandbox")
        self.assertEqual(normalize_portal_environment("production"), "production")
        self.assertEqual(normalize_portal_environment("prod"), "production")

    def test_resolve_settings_prefer_environment_specific_urls(self):
        env = {
            "FHIR_BASE_URL": "https://shared.example/FHIR/R4",
            "FHIR_TOKEN_URL": "https://shared.example/oauth2/token",
            "FHIR_CLIENT_ID": "shared-client",
            "FHIR_SANDBOX_BASE_URL": "https://sandbox.example/FHIR/R4",
            "FHIR_SANDBOX_CLIENT_ID": "sandbox-client",
            "FHIR_PRODUCTION_BASE_URL": "https://prod.example/FHIR/R4",
            "FHIR_PRODUCTION_TOKEN_URL": "https://prod.example/oauth2/token",
            "FHIR_PRODUCTION_CLIENT_ID": "prod-client",
            "FHIR_PATIENT_ID": "",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            sandbox = resolve_fhir_connection_settings("sandbox")
            production = resolve_fhir_connection_settings("production")

        self.assertEqual(sandbox["base_url"], "https://sandbox.example/FHIR/R4")
        self.assertEqual(sandbox["client_id"], "sandbox-client")
        self.assertEqual(sandbox["jwt_environment"], "nonprod")
        self.assertEqual(sandbox["default_patient_id"], EPIC_SANDBOX_TEST_PATIENT_ID)

        self.assertEqual(production["base_url"], "https://prod.example/FHIR/R4")
        self.assertEqual(production["token_url"], "https://prod.example/oauth2/token")
        self.assertEqual(production["client_id"], "prod-client")
        self.assertEqual(production["jwt_environment"], "production")
        self.assertIsNone(production["default_patient_id"])


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


class PatientSearchTests(unittest.TestCase):
    def test_map_patient_matches_extracts_mrn(self):
        bundle = {
            "resourceType": "Bundle",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "id": "pat-1",
                        "name": [{"family": "Smith", "given": ["Pat"]}],
                        "birthDate": "1980-01-02",
                        "gender": "female",
                        "identifier": [
                            {
                                "system": "urn:oid:1.2.3.4",
                                "value": "MRN-99",
                                "type": {"text": "MRN"},
                            }
                        ],
                    }
                }
            ],
        }
        matches = map_patient_matches(bundle, mrn_system="urn:oid:1.2.3.4")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].id, "pat-1")
        self.assertEqual(matches[0].display_name, "Pat Smith")
        self.assertEqual(matches[0].mrn, "MRN-99")
        self.assertEqual(matches[0].birthdate, "1980-01-02")

    def test_demo_search_by_mrn(self):
        client = DemoFHIRClient()
        matches = client.search_patients(mrn="DEMO-1002")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].display_name, "Alex Rivera")

    def test_demo_search_requires_criteria_for_live_contract(self):
        client = LiveFHIRClient(
            base_url="https://example.test/FHIR/R4",
            token_url="https://example.test/oauth2/token",
            client_id="client",
        )
        with self.assertRaises(ValueError):
            client.search_patients()


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

    def test_map_problems_and_diagnoses(self):
        bundle = {
            "resourceType": "Bundle",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Condition",
                        "id": "c1",
                        "code": {"text": "Hypertension"},
                        "category": [
                            {
                                "coding": [
                                    {
                                        "system": "http://terminology.hl7.org/CodeSystem/condition-category",
                                        "code": "problem-list-item",
                                    }
                                ]
                            }
                        ],
                        "clinicalStatus": {"text": "active"},
                        "verificationStatus": {"text": "confirmed"},
                        "onsetDateTime": "2015-01-01",
                    }
                },
                {
                    "resource": {
                        "resourceType": "Condition",
                        "id": "c2",
                        "code": {"text": "Acute bronchitis"},
                        "category": [
                            {
                                "coding": [
                                    {
                                        "system": "http://terminology.hl7.org/CodeSystem/condition-category",
                                        "code": "encounter-diagnosis",
                                    }
                                ]
                            }
                        ],
                        "clinicalStatus": {"text": "active"},
                        "verificationStatus": {"text": "confirmed"},
                    }
                },
            ],
        }
        problems = map_problems(bundle)
        diagnoses = map_diagnoses(bundle)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0].name, "Hypertension")
        self.assertEqual(len(diagnoses), 1)
        self.assertEqual(diagnoses[0].name, "Acute bronchitis")

    def test_map_medications(self):
        bundle = {
            "resourceType": "Bundle",
            "entry": [
                {
                    "resource": {
                        "resourceType": "MedicationRequest",
                        "id": "m1",
                        "status": "active",
                        "intent": "order",
                        "medicationCodeableConcept": {"text": "Metformin"},
                        "authoredOn": "2026-01-01",
                        "requester": {"display": "Dr. Rivera"},
                        "dosageInstruction": [{"text": "1 tablet twice daily"}],
                    }
                }
            ],
        }
        items = map_medications(bundle)
        self.assertEqual(items[0].name, "Metformin")
        self.assertEqual(items[0].dosage, "1 tablet twice daily")

    def test_map_allergies(self):
        bundle = {
            "resourceType": "Bundle",
            "entry": [
                {
                    "resource": {
                        "resourceType": "AllergyIntolerance",
                        "id": "a1",
                        "code": {"text": "Penicillin"},
                        "clinicalStatus": {"text": "active"},
                        "criticality": "high",
                        "category": ["medication"],
                        "reaction": [
                            {"manifestation": [{"text": "Hives"}], "severity": "severe"}
                        ],
                    }
                }
            ],
        }
        items = map_allergies(bundle)
        self.assertEqual(items[0].name, "Penicillin")
        self.assertIn("Hives", items[0].reaction)

    def test_map_provider_notes(self):
        bundle = {
            "resourceType": "Bundle",
            "entry": [
                {
                    "resource": {
                        "resourceType": "DocumentReference",
                        "id": "d1",
                        "status": "current",
                        "type": {"text": "Progress note"},
                        "description": "Office visit progress note",
                        "date": "2026-06-10",
                        "author": [{"display": "Dr. Rivera"}],
                    }
                }
            ],
        }
        items = map_provider_notes(bundle)
        self.assertEqual(items[0].title, "Office visit progress note")
        self.assertEqual(items[0].note_type, "Progress note")
        self.assertEqual(items[0].author, "Dr. Rivera")


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
            "Condition": {
                "resourceType": "Bundle",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "Condition",
                            "id": "c1",
                            "code": {"text": "Hypertension"},
                            "category": [
                                {
                                    "coding": [
                                        {
                                            "code": "problem-list-item",
                                            "display": "Problem List Item",
                                        }
                                    ]
                                }
                            ],
                            "clinicalStatus": {"text": "active"},
                            "verificationStatus": {"text": "confirmed"},
                        }
                    }
                ],
            },
            "MedicationRequest": {
                "resourceType": "Bundle",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "MedicationRequest",
                            "id": "m1",
                            "status": "active",
                            "intent": "order",
                            "medicationCodeableConcept": {"text": "Lisinopril"},
                        }
                    }
                ],
            },
            "AllergyIntolerance": {
                "resourceType": "Bundle",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "AllergyIntolerance",
                            "id": "a1",
                            "code": {"text": "Latex"},
                            "clinicalStatus": {"text": "active"},
                        }
                    }
                ],
            },
            "DocumentReference": {
                "resourceType": "Bundle",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "DocumentReference",
                            "id": "d1",
                            "status": "current",
                            "type": {"text": "Progress note"},
                            "description": "Follow-up note",
                            "date": "2026-06-10",
                        }
                    }
                ],
            },
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
        self.assertEqual(len(dashboard.problems), 1)
        self.assertEqual(dashboard.problems[0].name, "Hypertension")
        self.assertEqual(len(dashboard.medications), 1)
        self.assertEqual(dashboard.medications[0].name, "Lisinopril")
        self.assertEqual(len(dashboard.allergies), 1)
        self.assertEqual(dashboard.allergies[0].name, "Latex")
        self.assertEqual(len(dashboard.provider_notes), 1)
        self.assertEqual(dashboard.provider_notes[0].title, "Follow-up note")

    def test_fetch_dashboard_with_patient_access_token(self):
        client = LiveFHIRClient(
            "https://example.com/FHIR/R4",
            default_patient_id="pat-1",
        )

        def fake_get(path_or_url, access_token):
            self.assertEqual(access_token, "patient-token")
            if path_or_url.endswith("Patient/pat-1"):
                return {
                    "resourceType": "Patient",
                    "id": "pat-1",
                    "name": [{"family": "Patient", "given": ["Epic"]}],
                }
            return {"resourceType": "Bundle", "entry": []}

        with mock.patch.object(client, "_obtain_access_token") as obtain:
            with mock.patch.object(client, "_safe_get", side_effect=fake_get):
                dashboard = client.fetch_dashboard(
                    access_token="patient-token",
                    auth_method="patient_authorization_code",
                    grant_type="authorization_code",
                )
            obtain.assert_not_called()

        self.assertEqual(dashboard.connection.mode, "live")
        self.assertEqual(dashboard.connection.grant_type, "authorization_code")
        self.assertEqual(dashboard.connection.auth_method, "patient_authorization_code")
        self.assertEqual(dashboard.patient_display_name, "Epic Patient")


class PatientOauthHelperTests(unittest.TestCase):
    def test_generate_pkce_pair(self):
        from fhir.oauth import generate_pkce_pair

        pair = generate_pkce_pair()
        self.assertGreaterEqual(len(pair.code_verifier), 43)
        self.assertEqual(pair.code_challenge_method, "S256")
        self.assertNotEqual(pair.code_verifier, pair.code_challenge)

    def test_build_authorize_url(self):
        from fhir.oauth import build_authorize_url

        url = build_authorize_url(
            authorize_url="https://fhir.epic.com/oauth2/authorize",
            client_id="client-abc",
            redirect_uri="https://example.com/portal/epic/callback",
            scope="launch/patient patient/Patient.read",
            state="state-1",
            code_challenge="challenge-1",
            aud="https://fhir.epic.com/api/FHIR/R4",
        )
        self.assertIn("response_type=code", url)
        self.assertIn("client_id=client-abc", url)
        self.assertIn("code_challenge=challenge-1", url)
        self.assertIn("code_challenge_method=S256", url)
        self.assertIn("state=state-1", url)

    def test_request_authorization_code_token_pkce_public(self):
        from fhir.oauth import request_authorization_code_token

        captured = {}

        class FakeResponse:
            def read(self):
                return json.dumps(
                    {
                        "access_token": "pat-token",
                        "token_type": "Bearer",
                        "expires_in": 3600,
                        "patient": "erXuFYUfucBZaryVksYEcMg3",
                        "scope": "patient/Patient.read",
                    }
                ).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def fake_urlopen(request, timeout=30.0):
            captured["url"] = request.full_url
            captured["body"] = request.data.decode("utf-8")
            return FakeResponse()

        with mock.patch("fhir.oauth.urllib.request.urlopen", side_effect=fake_urlopen):
            token = request_authorization_code_token(
                token_url="https://fhir.epic.com/oauth2/token",
                client_id="client-abc",
                code="auth-code",
                redirect_uri="https://example.com/portal/epic/callback",
                code_verifier="verifier-xyz",
            )

        self.assertEqual(token.access_token, "pat-token")
        self.assertEqual(token.patient, "erXuFYUfucBZaryVksYEcMg3")
        self.assertIn("grant_type=authorization_code", captured["body"])
        self.assertIn("code_verifier=verifier-xyz", captured["body"])
        self.assertIn("client_id=client-abc", captured["body"])


class PortalEpicLoginRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app import create_app

        cls.app = create_app(run_migrate=False)
        cls.app.config["TESTING"] = True
        cls.app.config["WTF_CSRF_ENABLED"] = False

    def setUp(self):
        self.client = self.app.test_client()

    def test_login_page_renders_patient_mychart_entry(self):
        response = self.client.get("/portal/login")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Patient Portal", response.data)
        self.assertIn(b"MyChart", response.data)
        self.assertIn(b"Advocate / staff?", response.data)

    def test_dashboard_redirects_unauthenticated_to_portal_login(self):
        response = self.client.get("/portal/dashboard", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/portal/login", response.headers["Location"])

    def test_epic_login_redirects_when_configured(self):
        env = {
            "FHIR_AUTHORIZE_URL": "https://fhir.epic.com/oauth2/authorize",
            "FHIR_TOKEN_URL": "https://fhir.epic.com/oauth2/token",
            "FHIR_PATIENT_CLIENT_ID": "patient-client",
            "FHIR_BASE_URL": "https://fhir.epic.com/api/FHIR/R4",
            "PUBLIC_BASE_URL": "https://example.com",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            response = self.client.get("/portal/epic/login", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        location = response.headers["Location"]
        self.assertTrue(location.startswith("https://fhir.epic.com/oauth2/authorize?"))
        self.assertIn("client_id=patient-client", location)
        self.assertIn("code_challenge=", location)

    def test_epic_callback_stores_session(self):
        env = {
            "FHIR_TOKEN_URL": "https://fhir.epic.com/oauth2/token",
            "FHIR_PATIENT_CLIENT_ID": "patient-client",
            "PUBLIC_BASE_URL": "https://example.com",
        }

        with self.client.session_transaction() as sess:
            sess["epic_oauth_state"] = "good-state"
            sess["epic_code_verifier"] = "verifier-1"

        fake_token = mock.Mock(
            access_token="patient-access",
            patient="pat-99",
            scope="patient/Patient.read",
            expires_in=3600,
        )

        with mock.patch.dict(os.environ, env, clear=False):
            with mock.patch(
                "routes.portal.request_authorization_code_token",
                return_value=fake_token,
            ):
                response = self.client.get(
                    "/portal/epic/callback?code=abc&state=good-state",
                    follow_redirects=False,
                )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/portal/dashboard", response.headers["Location"])
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("epic_access_token"), "patient-access")
            self.assertEqual(sess.get("epic_patient_id"), "pat-99")


if __name__ == "__main__":
    unittest.main()
