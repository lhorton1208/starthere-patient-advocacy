-- StartHere ER schema (corrected reference)
-- Augments the existing Flask app schema; does NOT drop companies, advocates,
-- encounters, time_cards, lookup_lists, billings, or other current tables.
--
-- Client / patient rules:
--   - emailAddress UNIQUE on clients; UNIQUE on patients (separate namespaces).
--   - When client and patient are the same person, use the same email on both rows.
--   - Client may exist without a patient (clients.patientID NULL).
--   - Each patient row must reference exactly one client (patients.clientID NOT NULL).
--   - When linked, use optional clients.patientID -> patients.patientID (0..1 per client).

-- =============================================================================
-- CREATE TABLE (with datatype fixes applied)
-- =============================================================================

CREATE TABLE IF NOT EXISTS "clients" (
  "clientID" INTEGER NOT NULL PRIMARY KEY,
  "firstName" VARCHAR(255) NOT NULL,
  "lastName" VARCHAR(255) NOT NULL,  -- FIXED: was INTEGER
  "suffix" VARCHAR(10) NULL,
  "prefix" VARCHAR(255) NULL,
  "accountNumber" VARCHAR(255) NOT NULL,
  "address" VARCHAR(255) NOT NULL,
  "city" VARCHAR(255) NOT NULL,
  "state" VARCHAR(255) NOT NULL,
  "zipCode" VARCHAR(255) NOT NULL,
  "phoneNumber1" VARCHAR(32) NOT NULL,
  "phoneNumber2" VARCHAR(32) NULL,
  "relationshipToPatientID" INTEGER NULL,  -- FIXED: was VARCHAR FK mismatch
  "emailAddress" VARCHAR(255) NOT NULL UNIQUE,
  "middleName" VARCHAR(255) NULL,
  "patientID" INTEGER NULL
);

CREATE TABLE IF NOT EXISTS "patients" (
  "patientID" INTEGER NOT NULL PRIMARY KEY,
  "firstName" VARCHAR(255) NOT NULL,
  "middleName" VARCHAR(255) NULL,
  "lastName" VARCHAR(255) NOT NULL,
  "prefix" VARCHAR(32) NULL,
  "suffix" VARCHAR(32) NULL,
  "dob" DATE NOT NULL,
  "last4SSN" VARCHAR(4) NULL,  -- FIXED: VARCHAR(4) clearer than INTEGER for SSN fragment
  "lastEncounterDate" DATE NULL,
  "createdDate" DATE NOT NULL,
  "createdBy" VARCHAR(255) NOT NULL,
  "address" VARCHAR(255) NOT NULL,
  "city" VARCHAR(255) NOT NULL,
  "state" VARCHAR(255) NOT NULL,
  "zipCode" VARCHAR(255) NOT NULL,
  "emailAddress" VARCHAR(255) NOT NULL UNIQUE,
  "phoneNumberMobile" VARCHAR(32) NOT NULL,
  "phoneNumberLandLine" VARCHAR(32) NOT NULL,
  "mood" VARCHAR(255) NULL,
  "mentalState" VARCHAR(255) NULL,  -- FIXED: was INTEGER (unless coded lookup)
  "patientMedicationsID" INTEGER NULL,
  "clientID" INTEGER NOT NULL UNIQUE  -- ADDED UNIQUE: one patient row per client
);

CREATE TABLE IF NOT EXISTS "encounter" (
  "encounterID" INTEGER NOT NULL PRIMARY KEY,
  "encounterType" VARCHAR(255) NOT NULL,
  "hospitalID" INTEGER NULL,
  "advocateID" INTEGER NOT NULL,
  "patientID" INTEGER NOT NULL,
  "homeHealthCareFacilityID" INTEGER NULL
);

CREATE TABLE IF NOT EXISTS "notes" (
  "noteID" INTEGER NOT NULL PRIMARY KEY,
  "encounterID" INTEGER NULL,
  "patientID" INTEGER NOT NULL,
  "advocateID" INTEGER NOT NULL,
  "description" TEXT NOT NULL,
  "noteText" TEXT NOT NULL,
  "noteDateTime" TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS "advocate" (
  "advocateID" INTEGER NOT NULL PRIMARY KEY,
  "companyID" INTEGER NOT NULL,
  "FirstName" VARCHAR(255) NOT NULL,
  "middleName" VARCHAR(255) NULL,
  "lastName" VARCHAR(255) NOT NULL,
  "title" VARCHAR(255) NULL,
  "phoneNumberMobile" VARCHAR(32) NOT NULL,
  "phoneNumberLandLine" VARCHAR(32) NULL,
  "address" VARCHAR(255) NOT NULL,
  "city" VARCHAR(255) NOT NULL,
  "state" VARCHAR(255) NOT NULL,
  "zipCode" VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS "providers" (
  "providerID" INTEGER NOT NULL PRIMARY KEY,
  "locationID" INTEGER NULL,  -- FIXED: nullable until locations table exists
  "firstName" VARCHAR(255) NOT NULL,
  "middleName" VARCHAR(255) NULL,
  "lastName" VARCHAR(255) NOT NULL,
  "specialty" VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS "homeHealthFacilities" (
  "homeHealthFacilityID" INTEGER NOT NULL PRIMARY KEY,
  "facilityName" VARCHAR(255) NOT NULL,
  "address" VARCHAR(255) NOT NULL,
  "city" VARCHAR(255) NOT NULL,
  "state" VARCHAR(255) NOT NULL,
  "zipCode" VARCHAR(255) NOT NULL,
  "facilityPhoneNumber" VARCHAR(32) NOT NULL,
  "pointOfContactName" VARCHAR(255) NOT NULL,
  "pointOfContactPhoneNumber" VARCHAR(32) NOT NULL
);

CREATE TABLE IF NOT EXISTS "relationshipToPatient" (
  "relationshipToPatientID" INTEGER NOT NULL PRIMARY KEY,
  "relationship" VARCHAR(255) NOT NULL,
  "description" VARCHAR(255) NOT NULL,
  "isLegalGuardian" BOOLEAN NOT NULL,
  "isPowerOfAttorney" BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS "hospitals" (
  "hospitalID" INTEGER NOT NULL PRIMARY KEY,
  "hospitalName" VARCHAR(255) NOT NULL,
  "address" VARCHAR(255) NOT NULL,
  "city" VARCHAR(255) NOT NULL,
  "state" VARCHAR(255) NOT NULL,
  "zipCode" VARCHAR(255) NOT NULL,
  "mainPhoneNumber" VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS "accounts" (
  "accountID" INTEGER NOT NULL PRIMARY KEY,
  "billingAddress" VARCHAR(255) NOT NULL,
  "city" VARCHAR(255) NOT NULL,
  "state" VARCHAR(255) NOT NULL,
  "zipCode" VARCHAR(255) NOT NULL,
  "paymentMethod" VARCHAR(255) NOT NULL,
  "creditCardNumber" VARCHAR(64) NOT NULL,
  "expDate" VARCHAR(16) NOT NULL,
  "securityCode" INTEGER NOT NULL,
  "balance" DECIMAL(10, 2) NOT NULL,
  "lastPaymentDate" DATE NOT NULL,
  "accountNumber" VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS "invoices" (
  "invoicesID" INTEGER NOT NULL PRIMARY KEY,
  "accountID" INTEGER NOT NULL,
  "invoiceSubTotal" DECIMAL(10, 2) NOT NULL,
  "tax" DECIMAL(10, 2) NOT NULL,
  "invoiceTotal" DECIMAL(10, 2) NOT NULL,
  "Description" VARCHAR(255) NOT NULL,
  "invoiceDate" DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS "invoiceItems" (
  "invoiceItemID" INTEGER NOT NULL PRIMARY KEY,
  "invoiceID" INTEGER NOT NULL,
  "description" VARCHAR(255) NOT NULL,
  "lineItemTotal" DECIMAL(10, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS "patientMedications" (
  "patientMedicationsID" INTEGER NOT NULL PRIMARY KEY,
  "patientID" INTEGER NOT NULL,
  "medicationName" VARCHAR(255) NOT NULL,  -- FIXED: was INTEGER
  "description" TEXT NULL,
  "dosage" VARCHAR(255) NULL,
  "frequency" VARCHAR(255) NULL,
  "prescribedBy" VARCHAR(255) NULL,
  "isCompliant" BOOLEAN NULL,
  "pharmacy" VARCHAR(255) NULL,
  "pharmacyPhoneNumber" VARCHAR(32) NOT NULL,
  "address" VARCHAR(255) NOT NULL,
  "city" VARCHAR(255) NOT NULL,
  "state" VARCHAR(255) NOT NULL,
  "zipCode" VARCHAR(255) NOT NULL
);

-- =============================================================================
-- FOREIGN KEYS (corrected directions)
-- Remove any reversed FKs from your draft before applying these.
-- =============================================================================

-- Client <-> Patient (bidirectional optional link + required patient -> client)
ALTER TABLE "patients"
  ADD FOREIGN KEY ("clientID") REFERENCES "clients" ("clientID");
-- REMOVED (reversed): patients.patientID -> clients.patientID
ALTER TABLE "clients"
  ADD FOREIGN KEY ("patientID") REFERENCES "patients" ("patientID");

-- Client -> relationship lookup
-- REMOVED (type mismatch): clients.relationshipToPatient VARCHAR -> lookup ID
ALTER TABLE "clients"
  ADD FOREIGN KEY ("relationshipToPatientID") REFERENCES "relationshipToPatient" ("relationshipToPatientID");

-- Encounter
ALTER TABLE "encounter"
  ADD FOREIGN KEY ("patientID") REFERENCES "patients" ("patientID");
ALTER TABLE "encounter"
  ADD FOREIGN KEY ("advocateID") REFERENCES "advocate" ("advocateID");
ALTER TABLE "encounter"
  ADD FOREIGN KEY ("hospitalID") REFERENCES "hospitals" ("hospitalID");
-- REMOVED (reversed): homeHealthFacilities.homeHealthFacilityID -> encounter
ALTER TABLE "encounter"
  ADD FOREIGN KEY ("homeHealthCareFacilityID") REFERENCES "homeHealthFacilities" ("homeHealthFacilityID");

-- Notes
-- REMOVED (reversed): patients.patientID -> notes.patientID
ALTER TABLE "notes"
  ADD FOREIGN KEY ("patientID") REFERENCES "patients" ("patientID");
ALTER TABLE "notes"
  ADD FOREIGN KEY ("encounterID") REFERENCES "encounter" ("encounterID");
ALTER TABLE "notes"
  ADD FOREIGN KEY ("advocateID") REFERENCES "advocate" ("advocateID");

-- Billing
-- REMOVED (reversed): accounts.accountID -> invoices.accountID
ALTER TABLE "invoices"
  ADD FOREIGN KEY ("accountID") REFERENCES "accounts" ("accountID");
ALTER TABLE "invoiceItems"
  ADD FOREIGN KEY ("invoiceID") REFERENCES "invoices" ("invoicesID");

-- Medications
ALTER TABLE "patientMedications"
  ADD FOREIGN KEY ("patientID") REFERENCES "patients" ("patientID");
ALTER TABLE "patients"
  ADD FOREIGN KEY ("patientMedicationsID") REFERENCES "patientMedications" ("patientMedicationsID");

-- Advocate -> Company (existing app table; keep companies)
ALTER TABLE "advocate"
  ADD FOREIGN KEY ("companyID") REFERENCES "companies" ("id");

-- =============================================================================
-- UNIQUENESS (client/patient link + email policy)
-- =============================================================================

CREATE UNIQUE INDEX IF NOT EXISTS "uq_clients_patient_id"
  ON "clients" ("patientID")
  WHERE "patientID" IS NOT NULL;

-- patients.clientID already UNIQUE in CREATE above
