-- Migration: Add SFDC Lead URL tracking to sites table
-- Date: 2025-10-26
-- Description: Adds columns to track Salesforce Lead URLs for sites

ALTER TABLE sites ADD COLUMN sfdc_lead_url TEXT;
ALTER TABLE sites ADD COLUMN sfdc_lead_url_updated_at TEXT;

-- Create index for faster lookups when filtering by sites with SFDC leads
CREATE INDEX IF NOT EXISTS idx_sites_sfdc_lead_url ON sites(sfdc_lead_url) WHERE sfdc_lead_url IS NOT NULL;
