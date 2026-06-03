-- PostgreSQL augmentation migration for Render (reference).
-- Prefer: python scripts/migrate_schema.py (idempotent, used on app startup).
-- Preserves existing tables: companies, advocates, encounters, time_cards,
-- lookup_lists, billings, patient_relationships, etc.

-- New lookup / detail tables
CREATE TABLE IF NOT EXISTS relationship_to_patient (
  id SERIAL PRIMARY KEY,
  relationship VARCHAR(255) NOT NULL,
  description VARCHAR(255) NOT NULL,
  is_legal_guardian BOOLEAN NOT NULL DEFAULT FALSE,
  is_power_of_attorney BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS patient_medications (
  id SERIAL PRIMARY KEY,
  patient_id INTEGER NOT NULL REFERENCES patients(id),
  medication_name VARCHAR(255) NOT NULL,
  description TEXT,
  dosage VARCHAR(255),
  frequency VARCHAR(255),
  prescribed_by VARCHAR(255),
  is_compliant BOOLEAN,
  pharmacy VARCHAR(255),
  pharmacy_phone_number VARCHAR(32),
  address VARCHAR(255),
  city VARCHAR(255),
  state VARCHAR(255),
  zip_code VARCHAR(255),
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Example column adds (run via migrate_schema.py for full list)
-- ALTER TABLE clients ADD COLUMN IF NOT EXISTS patient_id INTEGER REFERENCES patients(id);
-- ALTER TABLE accounts ALTER COLUMN client_id SET NOT NULL;  -- after backfill

CREATE UNIQUE INDEX IF NOT EXISTS uq_clients_email
  ON clients (LOWER(TRIM(email))) WHERE email IS NOT NULL AND TRIM(email) <> '';

CREATE UNIQUE INDEX IF NOT EXISTS uq_patients_email
  ON patients (LOWER(TRIM(email))) WHERE email IS NOT NULL AND TRIM(email) <> '';

CREATE UNIQUE INDEX IF NOT EXISTS uq_patients_client_id ON patients (client_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_clients_patient_id
  ON clients (patient_id) WHERE patient_id IS NOT NULL;
